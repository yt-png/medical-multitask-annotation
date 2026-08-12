"""Parse Label Studio export JSON into ``TaskAnnotationResult`` (T4.1).

Supports SEG / DET / CAP exports aligned with package Labeling Configs.
Does not classify rework bundles, overwrite ``current/``, or re-import.
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
    DATA_KEY_MASK_REF,
    DATA_KEY_PACKAGE_ID,
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
)

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
) -> tuple[TaskAnnotationResult, ...]:
    """Load a Label Studio export JSON file and parse task results.

    When ``task_type`` is SEG and ``seg_manual_mask_dir`` is set, brush RLE
    results are decoded and written as ``{image_id}_manual.png`` under that
    directory; ``SegAnnotation.mask_ref`` becomes
    ``manual_masks/{image_id}_manual.png``. If the directory is omitted (unit
    tests / legacy callers), SEG keeps ``data.mask_ref`` even when brush
    results are present.
    """

    payload = read_json(path)
    return parse_ls_export_data(
        payload,
        task_type=task_type,
        image_metadata_by_id=image_metadata_by_id,
        seg_manual_mask_dir=seg_manual_mask_dir,
    )


def parse_ls_export_data(
    data: Any,
    *,
    task_type: TaskType,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None = None,
    seg_manual_mask_dir: Path | str | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Parse an in-memory Label Studio export payload (task list)."""

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")
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
    result_items = annotation.get("result")
    if not isinstance(result_items, list):
        raise ValueError(
            f"annotation result must be a list (image_id={image_id!r})"
        )

    _assert_task_controls_match(result_items, task_type=task_type, image_id=image_id)

    human_confirmed = _parse_required_choice(
        result_items,
        from_name=_FROM_HUMAN_CONFIRMED,
        image_id=image_id,
    )
    needs_rework = _parse_optional_choice(
        result_items,
        from_name=_FROM_NEEDS_REWORK,
        image_id=image_id,
        default=False,
    )

    payload = _parse_annotation_payload(
        result_items,
        task_type=task_type,
        image_id=image_id,
        task_data=data,
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
        export_round=None,
    )


def _select_annotation(annotations: Any, *, image_id: str) -> dict[str, Any]:
    if not isinstance(annotations, list) or not annotations:
        raise ValueError(f"no annotations for image_id={image_id!r}")

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
        raise ValueError(
            f"no non-cancelled annotations for image_id={image_id!r}"
        )

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


def _parse_required_choice(
    result_items: Sequence[Any],
    *,
    from_name: str,
    image_id: str,
) -> bool:
    matches = _choice_entries(
        result_items, from_name=from_name, image_id=image_id
    )
    if not matches:
        raise ValueError(
            f"missing required choice {from_name!r} (image_id={image_id!r})"
        )
    if len(matches) > 1:
        raise ValueError(
            f"duplicate choice control {from_name!r} (image_id={image_id!r})"
        )
    return _parse_choice_value(matches[0], image_id=image_id, from_name=from_name)


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
    result_items: Sequence[Any],
    *,
    task_type: TaskType,
    image_id: str,
    task_data: dict[str, Any],
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
    seg_manual_mask_dir: Path | str | None,
) -> SegAnnotation | DetAnnotation | CapAnnotation:
    if task_type is TaskType.SEG:
        return _parse_seg_annotation(
            result_items,
            task_data=task_data,
            image_id=image_id,
            seg_manual_mask_dir=seg_manual_mask_dir,
        )
    if task_type is TaskType.DET:
        return _parse_det_annotation(
            result_items,
            image_id=image_id,
            image_metadata_by_id=image_metadata_by_id,
        )
    if task_type is TaskType.CAP:
        return _parse_cap_annotation(result_items, image_id=image_id)
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover


def _parse_seg_annotation(
    result_items: Sequence[Any],
    *,
    task_data: dict[str, Any],
    image_id: str,
    seg_manual_mask_dir: Path | str | None,
) -> SegAnnotation:
    """Build SEG payload: prefer brush RLE when ``seg_manual_mask_dir`` is set."""

    from mma.converters.seg_brush import write_manual_mask_from_brush_results

    fallback_ref = task_data.get(DATA_KEY_MASK_REF)
    if not isinstance(fallback_ref, str) or not fallback_ref.strip():
        raise ValueError(
            f"SEG requires non-empty data.{DATA_KEY_MASK_REF} "
            f"(image_id={image_id!r})"
        )
    fallback_ref = fallback_ref.strip()

    brush_entries = _collect_seg_brush_entries(result_items, image_id=image_id)
    if not brush_entries or seg_manual_mask_dir is None:
        return SegAnnotation(mask_ref=fallback_ref)

    mask_ref = write_manual_mask_from_brush_results(
        brush_entries,
        image_id=image_id,
        manual_mask_dir=seg_manual_mask_dir,
    )
    return SegAnnotation(mask_ref=mask_ref)


def _collect_seg_brush_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect SEG brush results using DEFAULT_LS_RESULT_SPECS style.

    Primary match: ``from_name == seg_mask`` and ``value.format == "rle"``.
    ``type`` may be missing or equal to the configured brush type (DET/CAP style).
    """

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]
    from_name = spec["from_name"]
    expected_type = spec["type"]
    entries: list[dict[str, Any]] = []
    for entry in _iter_result_items(result_items, image_id=image_id):
        if entry.get("from_name") != from_name:
            continue
        if entry.get("type") not in (None, expected_type):
            raise ValueError(
                f"SEG result type must be {expected_type!r} "
                f"(image_id={image_id!r}, got {entry.get('type')!r})"
            )
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"SEG brush value must be an object (image_id={image_id!r})"
            )
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
        entries.append(entry)
    return entries


def _parse_det_annotation(
    result_items: Sequence[Any],
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
) -> DetAnnotation:
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.DET]
    from_name = spec["from_name"]
    expected_type = spec["type"]

    boxes: list[BBox] = []
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
        boxes.append(
            _percent_bbox_to_pixel(
                value,
                image_id=image_id,
                image_metadata_by_id=image_metadata_by_id,
            )
        )
    return DetAnnotation(bboxes=tuple(boxes))


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


def _parse_cap_annotation(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> CapAnnotation:
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]
    from_name = spec["from_name"]
    expected_type = spec["type"]

    matches = [
        entry
        for entry in _iter_result_items(result_items, image_id=image_id)
        if entry.get("from_name") == from_name
    ]
    if not matches:
        raise ValueError(
            f"CAP missing {from_name!r} textarea result (image_id={image_id!r})"
        )
    if len(matches) > 1:
        raise ValueError(
            f"CAP duplicate {from_name!r} textarea result (image_id={image_id!r})"
        )

    entry = matches[0]
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
    text = value.get("text")
    caption = _normalize_cap_text(text, image_id=image_id)
    return CapAnnotation(caption=caption)


def _normalize_cap_text(text: Any, *, image_id: str) -> str:
    if isinstance(text, str):
        caption = text.strip()
    elif isinstance(text, list):
        parts = [str(part).strip() for part in text if str(part).strip()]
        caption = parts[0] if parts else ""
    else:
        raise ValueError(
            f"CAP text must be a string or list of strings (image_id={image_id!r})"
        )
    if not caption:
        raise ValueError(f"CAP caption is empty (image_id={image_id!r})")
    return caption
