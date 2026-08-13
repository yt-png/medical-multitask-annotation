"""Parse Label Studio export JSON into ``TaskAnnotationResult`` (T4.1).

Supports SEG / DET / CAP exports aligned with package Labeling Configs.
Does not classify rework bundles, overwrite ``current/``, or re-import.

SEG human-priority rule: annotation SEG operation (``seg_mask`` entries and/or
``annotation.prediction`` link) wins over ``data.mask_ref``; zero brushes after
an operation yields an empty manual mask, not a prelabel fallback.

DET human-priority rule (three-way, mirrors SEG ``prediction`` link semantics):

1. ``annotation.result`` has ``det_bbox`` → use those boxes
2. no ``det_bbox`` but ``annotation.prediction`` is set → empty boxes
   (accepted prelabel then cleared all rectangles)
3. no ``det_bbox`` and ``annotation.prediction`` is null → fallback to
   ``task.predictions[].result`` det boxes; if none → empty boxes
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
        task=task,
        annotation=annotation,
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
    task: Mapping[str, Any] | None = None,
    annotation: Mapping[str, Any] | None = None,
) -> SegAnnotation | DetAnnotation | CapAnnotation:
    if task_type is TaskType.SEG:
        return _parse_seg_annotation(
            result_items,
            task_data=task_data,
            image_id=image_id,
            seg_manual_mask_dir=seg_manual_mask_dir,
            task=task,
            annotation=annotation,
        )
    if task_type is TaskType.DET:
        return _parse_det_annotation(
            result_items,
            image_id=image_id,
            image_metadata_by_id=image_metadata_by_id,
            task=task,
            annotation=annotation,
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
    task: Mapping[str, Any] | None = None,
    annotation: Mapping[str, Any] | None = None,
) -> SegAnnotation:
    """Build SEG payload with human-result priority.

    Label Studio SEG export shape (relevant fields)::

        {
          "data": {"mask_ref": "...", "image_id": "..."},
          "annotations": [{
            "prediction": <id|null>,   # set when annotation was created from a prediction
            "result": [
              {"from_name": "seg_mask", "type": "brushlabels", "value": {"format": "rle", "rle": [...]}},
              {"from_name": "human_confirmed", ...},
              ...
            ]
          }],
          "predictions": [{"result": [ /* prelabel brushes */ ]}]  # optional; may be ids only
        }

    Decision (not ``if not brush_entries: fallback`` alone):

    1. If annotation has a SEG operation record → human result.
       Operation record means any ``from_name=seg_mask`` entry (including empty
       ``rle``) **or** ``annotation.prediction`` is set (accepted prediction then
       possibly cleared all brushes).
       - Non-empty brushes → decode/write manual mask
       - Zero brushes → write an empty (all-background) manual mask
    2. Else → fallback to ``data.mask_ref`` (prelabel / prediction path)

    When ``seg_manual_mask_dir`` is omitted, human brush/empty masks are not
    written and the prelabel ``mask_ref`` is kept (legacy / unit-test path).
    """

    from mma.converters.seg_brush import (
        write_empty_manual_mask,
        write_manual_mask_from_brush_results,
    )

    fallback_ref = task_data.get(DATA_KEY_MASK_REF)
    if not isinstance(fallback_ref, str) or not fallback_ref.strip():
        raise ValueError(
            f"SEG requires non-empty data.{DATA_KEY_MASK_REF} "
            f"(image_id={image_id!r})"
        )
    fallback_ref = fallback_ref.strip()

    control_entries = _collect_seg_control_entries(result_items, image_id=image_id)
    brush_entries = [
        entry
        for entry in control_entries
        if _seg_entry_has_nonempty_rle(entry)
    ]
    operated = _annotation_has_seg_operation(
        control_entries,
        annotation=annotation,
    )

    if not operated:
        return SegAnnotation(mask_ref=fallback_ref)

    if seg_manual_mask_dir is None:
        # Human SEG intent detected but no output dir: keep legacy fallback.
        return SegAnnotation(mask_ref=fallback_ref)

    if brush_entries:
        mask_ref = write_manual_mask_from_brush_results(
            brush_entries,
            image_id=image_id,
            manual_mask_dir=seg_manual_mask_dir,
        )
        return SegAnnotation(mask_ref=mask_ref)

    width, height = _resolve_empty_mask_size(
        control_entries,
        task=task,
        image_id=image_id,
    )
    mask_ref = write_empty_manual_mask(
        image_id=image_id,
        width=width,
        height=height,
        manual_mask_dir=seg_manual_mask_dir,
    )
    return SegAnnotation(mask_ref=mask_ref)


def _annotation_has_seg_operation(
    control_entries: Sequence[dict[str, Any]],
    *,
    annotation: Mapping[str, Any] | None,
) -> bool:
    """Return True when the annotation records a SEG human operation.

    Signals (either is enough):

    - Any ``from_name=seg_mask`` result (including empty ``rle`` clear markers)
    - ``annotation.prediction`` is not null (annotation created from a
      prediction; deleting all brushes leaves no ``seg_mask`` items but the
      prediction link remains)
    """

    if control_entries:
        return True
    if annotation is None:
        return False
    return annotation.get("prediction") is not None


def _seg_entry_has_nonempty_rle(entry: Mapping[str, Any]) -> bool:
    value = entry.get("value")
    if not isinstance(value, dict):
        return False
    rle = value.get("rle")
    return isinstance(rle, list) and len(rle) > 0


def _collect_seg_control_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect all SEG brush control results (``from_name=seg_mask``).

    Empty ``rle`` lists are kept as clear markers (SEG operated, zero brushes).
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
        rle = value.get("rle")
        if not isinstance(rle, list):
            raise ValueError(
                f"SEG brush value.rle must be a list "
                f"(image_id={image_id!r})"
            )
        entries.append(entry)
    return entries


def _collect_seg_brush_entries(
    result_items: Sequence[Any],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect SEG brush results with non-empty RLE (DEFAULT_LS_RESULT_SPECS)."""

    return [
        entry
        for entry in _collect_seg_control_entries(result_items, image_id=image_id)
        if _seg_entry_has_nonempty_rle(entry)
    ]


def _resolve_empty_mask_size(
    control_entries: Sequence[Mapping[str, Any]],
    *,
    task: Mapping[str, Any] | None,
    image_id: str,
) -> tuple[int, int]:
    """Resolve width/height for an empty human mask."""

    for entry in control_entries:
        size = _try_entry_original_size(entry)
        if size is not None:
            return size

    if task is not None:
        predictions = task.get("predictions")
        if isinstance(predictions, list):
            for prediction in predictions:
                if not isinstance(prediction, dict):
                    continue
                result = prediction.get("result")
                if not isinstance(result, list):
                    continue
                for entry in result:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("from_name") != DEFAULT_LS_RESULT_SPECS[TaskType.SEG][
                        "from_name"
                    ]:
                        continue
                    size = _try_entry_original_size(entry)
                    if size is not None:
                        return size

    raise ValueError(
        f"cannot determine empty SEG mask size (image_id={image_id!r}); "
        "need original_width/original_height on a seg_mask entry or prediction"
    )


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
    result_items: Sequence[Any],
    *,
    image_id: str,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None,
    task: Mapping[str, Any] | None = None,
    annotation: Mapping[str, Any] | None = None,
) -> DetAnnotation:
    """Build DET payload with three-way human / cleared / prediction fallback.

    Label Studio DET export shape (relevant fields)::

        {
          "annotations": [{
            "prediction": <id|null>,  # set when annotation was created from a prediction
            "result": [
              {"from_name": "det_bbox", "type": "rectanglelabels", "value": {...}},
              {"from_name": "human_confirmed", ...},
              ...
            ]
          }],
          "predictions": [{"result": [ /* prelabel rectangles */ ]}]
        }

    Decision:

    1. Annotation has ``det_bbox`` entries → use those (human kept / edited boxes)
    2. No ``det_bbox`` but ``annotation.prediction`` is set → empty boxes
       (accepted prediction then deleted all rectangles)
    3. No ``det_bbox`` and ``annotation.prediction`` is null → fallback to
       ``task.predictions`` det boxes; if none → empty boxes
    """

    ann_entries = _collect_det_bbox_entries(result_items, image_id=image_id)
    if ann_entries:
        return DetAnnotation(
            bboxes=_det_entries_to_bboxes(
                ann_entries,
                image_id=image_id,
                image_metadata_by_id=image_metadata_by_id,
            )
        )

    if annotation is not None and annotation.get("prediction") is not None:
        return DetAnnotation(bboxes=())

    pred_entries = _collect_det_bbox_entries_from_predictions(
        task,
        image_id=image_id,
    )
    if not pred_entries:
        return DetAnnotation(bboxes=())
    return DetAnnotation(
        bboxes=_det_entries_to_bboxes(
            pred_entries,
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


def _collect_det_bbox_entries_from_predictions(
    task: Mapping[str, Any] | None,
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    """Collect DET boxes from ``task.predictions[].result`` (prelabel fallback)."""

    if task is None:
        return []
    predictions = task.get("predictions")
    if not isinstance(predictions, list):
        return []

    entries: list[dict[str, Any]] = []
    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue
        result = prediction.get("result")
        if not isinstance(result, list):
            continue
        entries.extend(
            _collect_det_bbox_entries(result, image_id=image_id)
        )
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
