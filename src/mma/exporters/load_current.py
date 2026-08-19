"""Load ``results/.../current/annotations.json`` for P5 merge (T4.5).

Read-only. Does not overwrite current, classify rework, or validate readiness.
"""

from __future__ import annotations

from pathlib import Path

from mma.common.models import TaskAnnotationResult, TaskType
from mma.common.paths import default_data_root, results_current_dir, validate_batch_id
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    read_annotations_json,
)


def load_current_annotations_file(
    path: Path | str,
    *,
    task_type: TaskType,
) -> tuple[TaskAnnotationResult, ...]:
    """Load a ``current/annotations.json`` file by explicit path.

    Missing file raises ``FileNotFoundError``.
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")
    return read_annotations_json(path, task_type=task_type)


def load_current(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path | str | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Load current effective results for one batch task.

    Path: ``{data_root}/results/{batch_id}/{seg|det|cap}/current/annotations.json``.
    Missing file raises ``FileNotFoundError``.
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    path = results_current_dir(cleaned, task_type, data_root=root) / (
        ANNOTATIONS_JSON_NAME
    )
    return read_annotations_json(
        path,
        task_type=task_type,
        batch_id=cleaned,
        data_root=root,
    )
