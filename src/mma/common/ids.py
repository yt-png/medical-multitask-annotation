"""Deterministic ID helpers for the annotation pipeline."""

from __future__ import annotations

from mma.common.models import TaskType

_TASK_DIR_BY_TYPE = {
    TaskType.SEG: "seg",
    TaskType.DET: "det",
    TaskType.CAP: "cap",
    "SEG": "seg",
    "DET": "det",
    "CAP": "cap",
    "seg": "seg",
    "det": "det",
    "cap": "cap",
}


def _assert_non_empty_batch_id(batch_id: str) -> None:
    if not batch_id or not batch_id.strip():
        raise ValueError("batch_id must be a non-empty string")


def generate_image_id(batch_id: str, sequence: int) -> str:
    """Build a deterministic image id: ``{batch_id}__{sequence:06d}``.

    ``sequence`` is 1-based. IDs are unique within a batch when sequences
    are unique.
    """

    _assert_non_empty_batch_id(batch_id)
    if sequence < 1:
        raise ValueError(f"sequence must be >= 1, got {sequence}")
    return f"{batch_id.strip()}__{sequence:06d}"


def generate_package_id(batch_id: str, task_type: TaskType | str) -> str:
    """Build a deterministic package id: ``{batch_id}__{seg|det|cap}``."""

    _assert_non_empty_batch_id(batch_id)
    key: TaskType | str = (
        task_type if isinstance(task_type, TaskType) else str(task_type)
    )
    try:
        task_dir = _TASK_DIR_BY_TYPE[key]
    except KeyError as exc:
        raise ValueError(f"unsupported task type: {task_type!r}") from exc
    return f"{batch_id.strip()}__{task_dir}"
