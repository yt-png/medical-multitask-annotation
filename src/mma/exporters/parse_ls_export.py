"""Parse Label Studio export JSON into ``TaskAnnotationResult`` (T4.1).

Supports SEG / DET / CAP exports aligned with package Labeling Configs.
Does not classify rework bundles, overwrite ``current/``, or re-import.

Effective payload selection is owned solely by ``resolve_effective_result``
(annotation-only). CAP / DET / SEG parsers only convert ``EffectiveLsResult``
into annotation objects and must not re-read ``task["predictions"]`` or use
``data.mask_ref`` / prediction geometry as the gold-standard source.

Empty / missing / cancelled-only ``annotations``, or empty ``result``, parse
as an empty payload (``human_confirmed`` defaults false) so classification
can send the sample to ``rework/`` instead of failing the whole export.

SEG: geometry or empty/confirm-only / human_cleared / unsubmitted → write
``manual_masks/`` (requires ``seg_manual_mask_dir``). Empty mask size comes
from annotation control ``original_*`` or ``image_metadata_by_id``.

DET: boxes from ``effective_result`` only (confirm-only / cleared → empty).

CAP: caption from ``effective_result``; missing ``cap_text`` → empty string.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mma.common.io import read_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.converters.to_labelstudio import (
    DATA_KEY_IMAGE_ID,
    DATA_KEY_PACKAGE_ID,
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
)
from mma.exporters.effective_result import EffectiveLsResult, resolve_effective_result


_CHOICE_YES = "yes"
_CHOICE_NO = "no"
_FROM_HUMAN_CONFIRMED = "human_confirmed"
_FROM_NEEDS_REWORK = "needs_rework"


def parse_ls_export(
    path: Path | str,
    *,
    task_type: TaskType,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None = None,
    seg_manual_mask_dir: Path | str | None = None,
    export_round: int | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Load a Label Studio export JSON file and parse task results.

    When ``task_type`` is SEG, ``seg_manual_mask_dir`` is required so human
    geometry or empty masks can be written as
    ``manual_masks/{image_id}_manual.png``. Empty-mask sizing uses annotation
    ``original_width/height`` or ``image_metadata_by_id``.

    ``export_round`` is a traceability field only (does not affect
    classification or merge). Callers such as ``apply-current`` typically
    derive it via ``parse_export_round_from_path``.
    """

    payload = read_json(path)
    return parse_ls_export_data(
        payload,
        task_type=task_type,
        image_metadata_by_id=image_metadata_by_id,
        seg_manual_mask_dir=seg_manual_mask_dir,
        export_round=export_round,
    )


def parse_ls_export_data(
    data: Any,
    *,
    task_type: TaskType,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None = None,
    seg_manual_mask_dir: Path | str | None = None,
    export_round: int | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Parse an in-memory Label Studio export payload (task list)."""

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")
    if export_round is not None and (
        not isinstance(export_round, int) or isinstance(export_round, bool)
    ):
        raise ValueError(
            f"export_round must be int or None, got {type(export_round)!r}"
        )
    if not isinstance(data, list):
        raise ValueError(
            f"Label Studio export must be a JSON array, got {type(data).__name__}"
        )

    results: list[TaskAnnotationResult] = []
    seen_image_ids: set[str] = set()
    for index, task in enumerate(data):
        if not isinstance(task, dict):
            raise ValueError(
                f"export task at index {index} must be an object, "
                f"got {type(task).__name__}"
            )
        parsed = _parse_one_task(
            task,
            task_type=task_type,
            image_metadata_by_id=image_metadata_by_id,
            seg_manual_mask_dir=seg_manual_mask_dir,
            export_round=export_round,
            index=index,
        )
        if parsed.image_id in seen_image_ids:
            raise ValueError(f"duplicate image_id in export: {parsed.image_id!r}")
        seen_image_ids.add(parsed.image_id)
        results.append(parsed)
    return tuple(results)


def _parse_one_task(
    task: dict[str, Any],
    *,
    task_type: TaskType,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
    seg_manual_mask_dir: Path | str | None,
    export_round: int | None,
    index: int,
) -> TaskAnnotationResult:
    data = task.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"export task at index {index} missing object field 'data'")

    image_id = data.get(DATA_KEY_IMAGE_ID)
    if not isinstance(image_id, str) or not image_id.strip():
        raise ValueError(
            f"export task at index {index} missing non-empty data.{DATA_KEY_IMAGE_ID}"
        )
    image_id = image_id.strip()

    annotation = _select_annotation(task.get("annotations"), image_id=image_id)
    effective = resolve_effective_result(
        task,
        task_type=task_type,
        image_id=image_id,
        annotation=annotation,
    )
    # Choices come from the coerced annotation.result (missing confirmed → false).
    choice_items = list(effective.annotation_result)

    _assert_task_controls_match(choice_items, task_type=task_type, image_id=image_id)
    _assert_task_controls_match(
        list(effective.effective_result),
        task_type=task_type,
        image_id=image_id,
    )

    human_confirmed = _parse_optional_choice(
        choice_items,
        from_name=_FROM_HUMAN_CONFIRMED,
        image_id=image_id,
        default=False,
    )
    needs_rework = _parse_optional_choice(
        choice_items,
        from_name=_FROM_NEEDS_REWORK,
        image_id=image_id,
        default=False,
    )

    payload = _parse_annotation_payload(
        effective,
        task_type=task_type,
        image_id=image_id,
        image_metadata_by_id=image_metadata_by_id,
        seg_manual_mask_dir=seg_manual_mask_dir,
    )

    package_id_raw = data.get(DATA_KEY_PACKAGE_ID)
    package_id: str | None
    if package_id_raw is None:
        package_id = None
    elif isinstance(package_id_raw, str) and package_id_raw.strip():
        package_id = package_id_raw.strip()
    else:
        raise ValueError(
            f"data.{DATA_KEY_PACKAGE_ID} must be a non-empty string when present "
            f"(image_id={image_id!r})"
        )

    return TaskAnnotationResult(
        image_id=image_id,
        task_type=task_type,
        annotation=payload,
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
        package_id=package_id,
        export_round=export_round,
    )


def _empty_annotation_sentinel() -> dict[str, Any]:
    """Return a stand-in annotation for missing / cancelled-only LS tasks."""

    return {"result": [], "was_cancelled": False}


def _select_annotation(annotations: Any, *, image_id: str) -> dict[str, Any]:
    """Pick the latest non-cancelled annotation, or an empty sentinel.

    ``None`` / ``[]`` / all-cancelled → empty ``result`` (V1: classify as
    rework). A non-list value is illegal JSON shape and still raises.
    """

    if annotations is None:
        return _empty_annotation_sentinel()
    if not isinstance(annotations, list):
        raise ValueError(
            f"annotations must be a list (image_id={image_id!r})"
        )
    if not annotations:
        return _empty_annotation_sentinel()

    candidates: list[dict[str, Any]] = []
    for item in annotations:
        if not isinstance(item, dict):
            raise ValueError(
                f"annotation entry must be an object (image_id={image_id!r})"
            )
        if item.get("was_cancelled") is True:
            continue
        candidates.append(item)

    if not candidates:
        return _empty_annotation_sentinel()

    def sort_key(item: dict[str, Any]) -> tuple[str, int]:
        updated = item.get("updated_at")
        updated_s = updated if isinstance(updated, str) else ""
        ann_id = item.get("id")
        ann_id_i = ann_id if isinstance(ann_id, int) else -1
        return (updated_s, ann_id_i)

    return max(candidates, key=sort_key)


def _assert_task_controls_match(
    result_items: Sequence[Any],
    *,
    task_type: TaskType,
    image_id: str,
) -> None:
    expected = DEFAULT_LS_RESULT_SPECS[task_type]["from_name"]
    foreign = {
        TaskType.SEG: DEFAULT_LS_RESULT_SPECS[TaskType.SEG]["from_name"],
        TaskType.DET: DEFAULT_LS_RESULT_SPECS[TaskType.DET]["from_name"],
        TaskType.CAP: DEFAULT_LS_RESULT_SPECS[TaskType.CAP]["from_name"],
    }
    found_foreign: set[str] = set()
    for item in result_items:
        if not isinstance(item, dict):
            continue
        from_name = item.get("from_name")
        if not isinstance(from_name, str):
            continue
        for other_type, control in foreign.items():
            if other_type is task_type:
                continue
            if from_name == control:
                found_foreign.add(from_name)
    if found_foreign:
        raise ValueError(
            f"export controls {sorted(found_foreign)!r} do not match "
            f"task_type={task_type.value} (expected {expected!r}, "
            f"image_id={image_id!r})"
        )


def _iter_result_items(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in result_items:
        if not isinstance(entry, dict):
            raise ValueError(
                f"annotation result entry must be an object (image_id={image_id!r})"
            )
        items.append(entry)
    return items


def _choice_entries(
    result_items: Sequence[Any],
    *,
    from_name: str,
    image_id: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for entry in _iter_result_items(result_items, image_id=image_id):
        if entry.get("from_name") == from_name:
            matches.append(entry)
    return matches


def _parse_choice_value(entry: dict[str, Any], *, image_id: str, from_name: str) -> bool:
    value = entry.get("value")
    if not isinstance(value, dict):
        raise ValueError(
            f"choices value must be an object for {from_name!r} "
            f"(image_id={image_id!r})"
        )
    choices = value.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(
            f"missing choices for {from_name!r} (image_id={image_id!r})"
        )
    raw = choices[0]
    if not isinstance(raw, str):
        raise ValueError(
            f"invalid choice for {from_name!r}: {raw!r} (image_id={image_id!r})"
        )
    normalized = raw.strip().lower()
    if normalized == _CHOICE_YES:
        return True
    if normalized == _CHOICE_NO:
        return False
    raise ValueError(
        f"invalid choice for {from_name!r}: {raw!r} "
        f"(expected {_CHOICE_YES!r} or {_CHOICE_NO!r}, image_id={image_id!r})"
    )


def _parse_optional_choice(
    result_items: Sequence[Any],
    *,
    from_name: str,
    image_id: str,
    default: bool,
) -> bool:
    matches = _choice_entries(
        result_items, from_name=from_name, image_id=image_id
    )
    if not matches:
        return default
    if len(matches) > 1:
        raise ValueError(
            f"duplicate choice control {from_name!r} (image_id={image_id!r})"
        )
    return _parse_choice_value(matches[0], image_id=image_id, from_name=from_name)


def _parse_annotation_payload(
    effective: EffectiveLsResult,
    *,
    task_type: TaskType,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
    seg_manual_mask_dir: Path | str | None,
) -> SegAnnotation | DetAnnotation | CapAnnotation:
    if task_type is TaskType.SEG:
        return _parse_seg_annotation(
            effective,
            image_id=image_id,
            image_metadata_by_id=image_metadata_by_id,
            seg_manual_mask_dir=seg_manual_mask_dir,
        )
    if task_type is TaskType.DET:
        return _parse_det_annotation(
            effective,
            image_id=image_id,
            image_metadata_by_id=image_metadata_by_id,
        )
    if task_type is TaskType.CAP:
        return _parse_cap_annotation(
            effective,
            image_id=image_id,
        )
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover


# SEG Label Studio control result types (brush history + polygon default).
_SEG_RESULT_TYPES = frozenset({"brushlabels", "polygonlabels"})


def _parse_seg_annotation(
    effective: EffectiveLsResult,
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
    seg_manual_mask_dir: Path | str | None,
) -> SegAnnotation:
    """Build SEG payload from annotation-only ``EffectiveLsResult``.

    Writes ``manual_masks/`` for human geometry or empty/confirm-only /
    human_cleared samples. Does not use ``data.mask_ref`` or prediction
    geometry as the gold-standard mask. Requires ``seg_manual_mask_dir``.
    """

    from mma.converters.seg_brush import write_empty_manual_mask
    from mma.converters.seg_polygon import write_manual_mask_from_seg_geometry

    if seg_manual_mask_dir is None:
        raise ValueError(
            "SEG parse requires seg_manual_mask_dir "
            f"(image_id={image_id!r})"
        )

    control_entries = _collect_seg_control_entries(
        list(effective.effective_result),
        image_id=image_id,
    )
    brush_entries = [
        entry
        for entry in control_entries
        if _seg_entry_has_nonempty_rle(entry)
    ]
    polygon_entries = [
        entry
        for entry in control_entries
        if _seg_entry_has_nonempty_points(entry)
    ]

    if brush_entries or polygon_entries:
        mask_ref = write_manual_mask_from_seg_geometry(
            image_id=image_id,
            manual_mask_dir=seg_manual_mask_dir,
            brush_entries=brush_entries,
            polygon_entries=polygon_entries,
        )
        return SegAnnotation(mask_ref=mask_ref, has_foreground=True)

    width, height = _resolve_empty_mask_size(
        control_entries,
        image_id=image_id,
        image_metadata_by_id=image_metadata_by_id,
    )
    mask_ref = write_empty_manual_mask(
        image_id=image_id,
        width=width,
        height=height,
        manual_mask_dir=seg_manual_mask_dir,
    )
    return SegAnnotation(mask_ref=mask_ref, has_foreground=False)


def _seg_entry_has_nonempty_rle(entry: Mapping[str, Any]) -> bool:
    value = entry.get("value")
    if not isinstance(value, dict):
        return False
    rle = value.get("rle")
    return isinstance(rle, list) and len(rle) > 0


def _seg_entry_has_nonempty_points(entry: Mapping[str, Any]) -> bool:
    value = entry.get("value")
    if not isinstance(value, dict):
        return False
    points = value.get("points")
    return isinstance(points, list) and len(points) >= 3


def _infer_seg_result_type(
    entry: Mapping[str, Any],
    *,
    image_id: str,
) -> str:
    """Resolve brush vs polygon type from ``type`` or ``value`` keys."""

    raw_type = entry.get("type")
    if raw_type in _SEG_RESULT_TYPES:
        return str(raw_type)
    if raw_type not in (None,):
        raise ValueError(
            f"SEG result type must be one of {sorted(_SEG_RESULT_TYPES)} "
            f"(image_id={image_id!r}, got {raw_type!r})"
        )

    value = entry.get("value")
    if not isinstance(value, dict):
        raise ValueError(
            f"SEG control value must be an object (image_id={image_id!r})"
        )
    has_rle = "rle" in value
    has_points = "points" in value
    if has_rle and not has_points:
        return "brushlabels"
    if has_points and not has_rle:
        return "polygonlabels"
    raise ValueError(
        "SEG control value must contain either rle (brushlabels) or "
        f"points (polygonlabels) (image_id={image_id!r})"
    )


def _validate_seg_brush_value(
    value: Mapping[str, Any],
    *,
    image_id: str,
) -> None:
    fmt = value.get("format")
    if fmt != "rle":
        raise ValueError(
            f"SEG brush value.format must be 'rle' "
            f"(image_id={image_id!r}, got {fmt!r})"
        )
    if "rle" not in value:
        raise ValueError(
            f"SEG brush value missing rle (image_id={image_id!r})"
        )
    rle = value.get("rle")
    if not isinstance(rle, list):
        raise ValueError(
            f"SEG brush value.rle must be a list "
            f"(image_id={image_id!r})"
        )


def _validate_seg_polygon_value(
    value: Mapping[str, Any],
    *,
    image_id: str,
) -> None:
    if "points" not in value:
        raise ValueError(
            f"SEG polygon value missing points (image_id={image_id!r})"
        )
    points = value.get("points")
    if not isinstance(points, list):
        raise ValueError(
            f"SEG polygon value.points must be a list "
            f"(image_id={image_id!r})"
        )
    for index, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(
                f"SEG polygon value.points[{index}] must be [x, y] "
                f"(image_id={image_id!r})"
            )


def _collect_seg_control_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect SEG control results (``from_name=seg_mask``).

    Accepts ``brushlabels`` (``value.rle``) and ``polygonlabels``
    (``value.points``). Empty ``rle`` / ``points`` lists are kept as clear
    markers (SEG operated, zero geometry).
    """

    from_name = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]["from_name"]
    entries: list[dict[str, Any]] = []
    for entry in _iter_result_items(result_items, image_id=image_id):
        if entry.get("from_name") != from_name:
            continue
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"SEG control value must be an object (image_id={image_id!r})"
            )
        result_type = _infer_seg_result_type(entry, image_id=image_id)
        if result_type == "brushlabels":
            _validate_seg_brush_value(value, image_id=image_id)
        else:
            _validate_seg_polygon_value(value, image_id=image_id)
        entries.append(entry)
    return entries


def _collect_seg_brush_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect SEG brush results with non-empty RLE (legacy helper)."""

    return [
        entry
        for entry in _collect_seg_control_entries(result_items, image_id=image_id)
        if _seg_entry_has_nonempty_rle(entry)
    ]


def _resolve_empty_mask_size(
    control_entries: Sequence[Mapping[str, Any]],
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> tuple[int, int]:
    """Resolve width/height for an empty human mask.

    Uses sizes on SEG control entries first, then ``image_metadata_by_id``.
    Does not read prediction results.
    """

    for entry in control_entries:
        size = _try_entry_original_size(entry)
        if size is not None:
            return size

    meta_size = _seg_size_from_image_metadata(
        image_id, image_metadata_by_id
    )
    if meta_size is not None:
        return meta_size

    raise ValueError(
        f"cannot determine empty SEG mask size (image_id={image_id!r}); "
        "need original_width/original_height on a seg_mask entry or "
        "image_metadata_by_id"
    )


def _seg_size_from_image_metadata(
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> tuple[int, int] | None:
    if image_metadata_by_id is None:
        return None
    metadata = image_metadata_by_id.get(image_id)
    if metadata is None:
        return None
    if not isinstance(metadata, ImageMetadata):
        raise ValueError(
            f"image_metadata for {image_id!r} must be ImageMetadata, "
            f"got {type(metadata).__name__}"
        )
    width = int(metadata.width)
    height = int(metadata.height)
    if width <= 0 or height <= 0:
        return None
    return width, height


def _try_entry_original_size(
    entry: Mapping[str, Any],
) -> tuple[int, int] | None:
    try:
        width = int(entry["original_width"])
        height = int(entry["original_height"])
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _parse_det_annotation(
    effective: EffectiveLsResult,
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> DetAnnotation:
    """Build DET payload from annotation-only ``EffectiveLsResult``.

    Boxes come from ``effective.effective_result`` only (confirm-only /
    human-cleared → empty). Does not read ``task["predictions"]``.
    """

    entries = _collect_det_bbox_entries(
        list(effective.effective_result),
        image_id=image_id,
    )
    if not entries:
        return DetAnnotation(bboxes=())
    return DetAnnotation(
        bboxes=_det_entries_to_bboxes(
            entries,
            image_id=image_id,
            image_metadata_by_id=image_metadata_by_id,
        )
    )


def _collect_det_bbox_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect ``from_name=det_bbox`` rectangle entries from a result list."""

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.DET]
    from_name = spec["from_name"]
    expected_type = spec["type"]
    entries: list[dict[str, Any]] = []
    for entry in _iter_result_items(result_items, image_id=image_id):
        if entry.get("from_name") != from_name:
            continue
        if entry.get("type") not in (None, expected_type):
            raise ValueError(
                f"DET result type must be {expected_type!r} "
                f"(image_id={image_id!r}, got {entry.get('type')!r})"
            )
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"DET rectangle value must be an object (image_id={image_id!r})"
            )
        entries.append(entry)
    return entries


def _det_entries_to_bboxes(
    entries: Sequence[Mapping[str, Any]],
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> tuple[BBox, ...]:
    boxes: list[BBox] = []
    for entry in entries:
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"DET rectangle value must be an object (image_id={image_id!r})"
            )
        boxes.append(
            _percent_bbox_to_pixel(
                value,
                image_id=image_id,
                image_metadata_by_id=image_metadata_by_id,
            )
        )
    return tuple(boxes)


def _require_det_metadata(
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> ImageMetadata:
    if image_metadata_by_id is None:
        raise ValueError(
            "DET conversion requires image_metadata_by_id "
            f"(image_id={image_id!r})"
        )
    metadata = image_metadata_by_id.get(image_id)
    if metadata is None:
        raise ValueError(
            "DET conversion missing image_metadata "
            f"(image_id={image_id!r})"
        )
    if not isinstance(metadata, ImageMetadata):
        raise ValueError(
            f"image_metadata for {image_id!r} must be ImageMetadata, "
            f"got {type(metadata).__name__}"
        )
    return metadata


def _percent_bbox_to_pixel(
    value: dict[str, Any],
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> BBox:
    metadata = _require_det_metadata(image_id, image_metadata_by_id)
    try:
        x_pct = float(value["x"])
        y_pct = float(value["y"])
        w_pct = float(value["width"])
        h_pct = float(value["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"DET rectangle missing numeric x/y/width/height "
            f"(image_id={image_id!r})"
        ) from exc

    return BBox(
        x=x_pct / 100.0 * metadata.width,
        y=y_pct / 100.0 * metadata.height,
        width=w_pct / 100.0 * metadata.width,
        height=h_pct / 100.0 * metadata.height,
    )


def _collect_cap_text_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect ``from_name=cap_text`` textarea entries (may have empty text)."""

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]
    from_name = spec["from_name"]
    expected_type = spec["type"]
    matches: list[dict[str, Any]] = []
    for entry in _iter_result_items(result_items, image_id=image_id):
        if entry.get("from_name") != from_name:
            continue
        if entry.get("type") not in (None, expected_type):
            raise ValueError(
                f"CAP result type must be {expected_type!r} "
                f"(image_id={image_id!r}, got {entry.get('type')!r})"
            )
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"CAP textarea value must be an object (image_id={image_id!r})"
            )
        if "text" not in value:
            raise ValueError(
                f"CAP textarea value missing text (image_id={image_id!r})"
            )
        matches.append(entry)
    return matches


def _parse_cap_annotation(
    effective: EffectiveLsResult,
    *,
    image_id: str,
) -> CapAnnotation:
    """Build CAP payload from annotation-only ``EffectiveLsResult``.

    Caption is taken from ``effective.effective_result``. Missing ``cap_text``
    (confirm-only or human-cleared) yields an empty caption.
    """

    entries = _collect_cap_text_entries(
        list(effective.effective_result),
        image_id=image_id,
    )
    if len(entries) > 1:
        raise ValueError(
            f"CAP duplicate {DEFAULT_LS_RESULT_SPECS[TaskType.CAP]['from_name']!r} "
            f"textarea result (image_id={image_id!r})"
        )
    if entries:
        text = entries[0]["value"].get("text")
        caption = _normalize_cap_text(
            text, image_id=image_id, allow_empty=True
        )
        return CapAnnotation(caption=caption)

    return CapAnnotation(caption="")


def _normalize_cap_text(
    text: Any,
    *,
    image_id: str,
    allow_empty: bool = False,
) -> str:
    """Normalize LS textarea ``text`` to a caption string.

    When ``allow_empty`` is True, empty / whitespace-only text becomes ``""``
    (human clear). When False, empty text raises (legacy strict callers).
    """

    if isinstance(text, str):
        caption = text.strip()
    elif isinstance(text, list):
        parts = [str(part).strip() for part in text if str(part).strip()]
        caption = parts[0] if parts else ""
    else:
        raise ValueError(
            f"CAP text must be a string or list of strings (image_id={image_id!r})"
        )
    if not caption and not allow_empty:
        raise ValueError(f"CAP caption is empty (image_id={image_id!r})")
    return caption
