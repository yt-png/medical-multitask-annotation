"""Extract Label Studio effective results by image_id (legacy rework channel).

Uses ``resolve_effective_result`` (annotation-only effective). Confirm-only
exports no longer carry prediction geometry/text. Prefer
``previous_annotations`` for rework prefill.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mma.common.io import read_json
from mma.common.models import TaskType
from mma.converters.to_labelstudio import DATA_KEY_IMAGE_ID
from mma.exporters.effective_result import resolve_effective_result
from mma.exporters.parse_ls_export import _select_annotation


def extract_ls_raw_results(
    path: Path | str,
    *,
    task_type: TaskType,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Load an LS export JSON file and return ``image_id -> effective result``."""

    payload = read_json(path)
    return extract_ls_raw_results_data(payload, task_type=task_type)


def extract_ls_raw_results_data(
    data: Any,
    *,
    task_type: TaskType,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Extract deep-copied **effective** result lists keyed by ``image_id``.

    Effective = annotation-only ``resolve_effective_result.effective_result``
    (confirm-only / cleared samples do not include prediction geometry).
    """

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
    effective = resolve_effective_result(
        task,
        task_type=task_type,
        image_id=image_id,
        annotation=annotation,
    )
    _assert_task_controls_match(
        list(effective.annotation_result),
        task_type=task_type,
        image_id=image_id,
    )
    _assert_task_controls_match(
        list(effective.effective_result),
        task_type=task_type,
        image_id=image_id,
    )
    return image_id, effective.effective_result


def _assert_task_controls_match(
    result_items: list[Any],
    *,
    task_type: TaskType,
    image_id: str,
) -> None:
    from mma.converters.to_labelstudio import DEFAULT_LS_RESULT_SPECS

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
