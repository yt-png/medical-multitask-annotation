"""Extract Label Studio raw annotation results by image_id (S2 side channel).

Selection rules align with ``parse_ls_export`` (non-cancelled, latest
``updated_at`` / ``id``). Does not change the T4.1 ``TaskAnnotationResult`` API.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from mma.common.io import read_json
from mma.common.models import TaskType
from mma.converters.to_labelstudio import (
    DATA_KEY_IMAGE_ID,
    DEFAULT_LS_RESULT_SPECS,
)


def extract_ls_raw_results(
    path: Path | str,
    *,
    task_type: TaskType,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Load an LS export JSON file and return ``image_id -> raw result``."""

    payload = read_json(path)
    return extract_ls_raw_results_data(payload, task_type=task_type)


def extract_ls_raw_results_data(
    data: Any,
    *,
    task_type: TaskType,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Extract deep-copied annotation ``result`` lists keyed by ``image_id``."""

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")
    if not isinstance(data, list):
        raise ValueError(
            f"Label Studio export must be a JSON array, got {type(data).__name__}"
        )

    by_image_id: dict[str, tuple[dict[str, Any], ...]] = {}
    for index, task in enumerate(data):
        if not isinstance(task, dict):
            raise ValueError(
                f"export task at index {index} must be an object, "
                f"got {type(task).__name__}"
            )
        image_id, raw_result = _extract_one_task(
            task, task_type=task_type, index=index
        )
        if image_id in by_image_id:
            raise ValueError(f"duplicate image_id in export: {image_id!r}")
        by_image_id[image_id] = raw_result
    return by_image_id


def _extract_one_task(
    task: dict[str, Any],
    *,
    task_type: TaskType,
    index: int,
) -> tuple[str, tuple[dict[str, Any], ...]]:
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

    copied: list[dict[str, Any]] = []
    for entry in result_items:
        if not isinstance(entry, dict):
            raise ValueError(
                f"annotation result entry must be an object (image_id={image_id!r})"
            )
        copied.append(copy.deepcopy(entry))
    return image_id, tuple(copied)


def _select_annotation(annotations: Any, *, image_id: str) -> dict[str, Any]:
    """Same selection policy as ``parse_ls_export._select_annotation``."""

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
    result_items: list[Any],
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
