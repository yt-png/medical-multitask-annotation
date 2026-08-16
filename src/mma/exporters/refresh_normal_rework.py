"""Rebuild ``normal/`` and ``rework/`` from ``current/`` (full replace).

``current/`` is the sole source of truth. Bundles are never appended from a
partial export; each refresh overwrites both annotation files completely.

Classification is delegated to ``split_by_rework`` → ``should_rework_result``
(choices plus empty / missing task payload → rework).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mma.common.io import write_json
from mma.common.models import TaskAnnotationResult, TaskType
from mma.common.paths import (
    default_data_root,
    results_current_dir,
    results_normal_dir,
    results_rework_dir,
    validate_batch_id,
)
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    task_annotation_result_to_dict,
)
from mma.exporters.load_current import load_current
from mma.exporters.previous_annotations import write_previous_annotations
from mma.exporters.split_by_rework import split_by_rework


def refresh_normal_rework_from_current(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path | str | None = None,
) -> tuple[Path, Path]:
    """Full-rebuild ``normal/`` and ``rework/`` from ``current/annotations.json``.

    - Missing ``current/`` → both sides written as ``[]``
    - Otherwise load current, ``split_by_rework`` (``should_rework_result``,
      including empty payload), overwrite both files

    Returns ``(normal_path, rework_path)``.
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    current_path = results_current_dir(cleaned, task_type, data_root=root) / (
        ANNOTATIONS_JSON_NAME
    )

    if current_path.is_file():
        results = load_current(cleaned, task_type, data_root=root)
    else:
        results = ()

    normal, rework = split_by_rework(results)
    return write_normal_rework_bundles(
        normal,
        rework,
        batch_id=cleaned,
        task_type=task_type,
        data_root=root,
    )


def write_normal_rework_bundles(
    normal: Sequence[TaskAnnotationResult],
    rework: Sequence[TaskAnnotationResult],
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path | str | None = None,
) -> tuple[Path, Path]:
    """Overwrite ``normal/`` + ``rework/`` annotations and rework snapshots.

    Also writes ``rework/previous_annotations/<task>.json`` (and SEG mask
    copies) from ``TaskAnnotationResult.annotation`` so the rework package is
    self-contained for ``rework-import`` without an LS export.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    normal_path = (
        results_normal_dir(cleaned, task_type, data_root=root) / ANNOTATIONS_JSON_NAME
    )
    rework_path = (
        results_rework_dir(cleaned, task_type, data_root=root) / ANNOTATIONS_JSON_NAME
    )
    _write_annotations_file(normal_path, normal)
    _write_annotations_file(rework_path, rework)
    write_previous_annotations(
        rework,
        batch_id=cleaned,
        task_type=task_type,
        data_root=root,
    )
    return normal_path.resolve(), rework_path.resolve()


def _write_annotations_file(
    path: Path,
    items: Sequence[TaskAnnotationResult],
) -> None:
    payload = [task_annotation_result_to_dict(item) for item in items]
    write_json(path, payload)
