"""Overwrite ``results/.../current/annotations.json`` (T4.4).

Persists ``TaskAnnotationResult`` records only (no separate business schema).
Same ``image_id`` within one task directory is replaced in place; new ids append.
Empty input is a no-op (does not clear existing current).
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mma.common.models import TaskAnnotationResult, TaskType
from mma.common.paths import default_data_root, results_current_dir, validate_batch_id
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    read_annotations_json,
    task_annotation_result_to_dict,
)


def overwrite_current(
    results: Sequence[TaskAnnotationResult],
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path | str | None = None,
) -> Path:
    """Merge ``results`` into ``current/annotations.json`` and return its path.

    - Matching ``image_id`` entries are replaced (annotation + checkbox fields).
    - New ``image_id`` values are appended after existing order.
    - Empty ``results`` leaves any existing file unchanged (no-op).
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    out_path = results_current_dir(cleaned, task_type, data_root=root) / (
        ANNOTATIONS_JSON_NAME
    )

    if not results:
        return out_path.resolve()

    incoming = _validate_incoming(results, task_type=task_type)
    existing = _read_existing_items(
        out_path,
        task_type=task_type,
        batch_id=cleaned,
        data_root=root,
    )
    merged = _merge_by_image_id(existing, incoming)
    _atomic_write_json(
        out_path,
        [task_annotation_result_to_dict(item) for item in merged],
    )
    return out_path.resolve()


def _validate_incoming(
    results: Sequence[TaskAnnotationResult],
    *,
    task_type: TaskType,
) -> list[TaskAnnotationResult]:
    validated: list[TaskAnnotationResult] = []
    seen: set[str] = set()
    for index, item in enumerate(results):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"results[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if item.task_type is not task_type:
            raise ValueError(
                f"item task_type {item.task_type.value} does not match "
                f"requested {task_type.value} (image_id={item.image_id!r})"
            )
        if item.image_id in seen:
            raise ValueError(
                f"duplicate image_id in overwrite batch: {item.image_id!r}"
            )
        seen.add(item.image_id)
        validated.append(item)
    return validated


def _merge_by_image_id(
    existing: list[TaskAnnotationResult],
    incoming: list[TaskAnnotationResult],
) -> list[TaskAnnotationResult]:
    incoming_by_id = {item.image_id: item for item in incoming}
    merged: list[TaskAnnotationResult] = []
    seen: set[str] = set()

    for item in existing:
        if item.image_id in incoming_by_id:
            merged.append(incoming_by_id[item.image_id])
        else:
            merged.append(item)
        seen.add(item.image_id)

    for item in incoming:
        if item.image_id not in seen:
            merged.append(item)
    return merged


def _read_existing_items(
    path: Path,
    *,
    task_type: TaskType,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
) -> list[TaskAnnotationResult]:
    """Load existing current items; missing file means empty list (overwrite)."""

    if not path.is_file():
        return []
    return list(
        read_annotations_json(
            path,
            task_type=task_type,
            batch_id=batch_id,
            data_root=data_root,
        )
    )


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
