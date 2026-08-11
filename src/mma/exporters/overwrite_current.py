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

from mma.common.io import read_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import default_data_root, results_current_dir, validate_batch_id

ANNOTATIONS_JSON_NAME = "annotations.json"


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
    existing = _read_existing_items(out_path, task_type=task_type)
    merged = _merge_by_image_id(existing, incoming)
    _atomic_write_json(out_path, [_result_to_dict(item) for item in merged])
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
) -> list[TaskAnnotationResult]:
    if not path.is_file():
        return []
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(
            f"current annotations.json must be a JSON array of "
            f"TaskAnnotationResult objects: {path}"
        )
    items: list[TaskAnnotationResult] = []
    seen: set[str] = set()
    for index, raw in enumerate(payload):
        item = _result_from_dict(raw, index=index)
        if item.task_type is not task_type:
            raise ValueError(
                f"existing current item task_type {item.task_type.value} "
                f"does not match requested {task_type.value} "
                f"(image_id={item.image_id!r})"
            )
        if item.image_id in seen:
            raise ValueError(
                f"duplicate image_id in existing current file: {item.image_id!r}"
            )
        seen.add(item.image_id)
        items.append(item)
    return items


def _result_to_dict(item: TaskAnnotationResult) -> dict[str, Any]:
    return {
        "image_id": item.image_id,
        "task_type": item.task_type.value,
        "annotation": _annotation_to_dict(item),
        "human_confirmed": item.human_confirmed,
        "needs_rework": item.needs_rework,
        "package_id": item.package_id,
        "export_round": item.export_round,
    }


def _annotation_to_dict(item: TaskAnnotationResult) -> dict[str, Any]:
    annotation = item.annotation
    if isinstance(annotation, SegAnnotation):
        return {"mask_ref": annotation.mask_ref}
    if isinstance(annotation, DetAnnotation):
        return {
            "bboxes": [
                {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                }
                for box in annotation.bboxes
            ]
        }
    if isinstance(annotation, CapAnnotation):
        return {"caption": annotation.caption}
    raise ValueError(  # pragma: no cover
        f"unsupported annotation type: {type(annotation).__name__}"
    )


def _result_from_dict(raw: Any, *, index: int) -> TaskAnnotationResult:
    if not isinstance(raw, dict):
        raise ValueError(
            f"current annotations item at index {index} must be an object"
        )
    try:
        image_id = str(raw["image_id"]).strip()
        task_type_raw = raw["task_type"]
        human_confirmed = raw["human_confirmed"]
        needs_rework = raw["needs_rework"]
        annotation_raw = raw["annotation"]
    except KeyError as exc:
        raise ValueError(
            f"current annotations item at index {index} missing field "
            f"{exc.args[0]!r}"
        ) from exc

    if not image_id:
        raise ValueError(
            f"current annotations item at index {index} has empty image_id"
        )
    if not isinstance(human_confirmed, bool) or not isinstance(needs_rework, bool):
        raise ValueError(
            f"human_confirmed/needs_rework must be bool "
            f"(image_id={image_id!r})"
        )

    try:
        task_type = TaskType(str(task_type_raw).strip())
    except ValueError as exc:
        raise ValueError(
            f"invalid task_type {task_type_raw!r} (image_id={image_id!r})"
        ) from exc

    package_id = raw.get("package_id")
    if package_id is not None and (
        not isinstance(package_id, str) or not package_id.strip()
    ):
        raise ValueError(
            f"package_id must be a non-empty string or null "
            f"(image_id={image_id!r})"
        )
    if isinstance(package_id, str):
        package_id = package_id.strip()

    export_round = raw.get("export_round")
    if export_round is not None and not isinstance(export_round, int):
        raise ValueError(
            f"export_round must be int or null (image_id={image_id!r})"
        )

    annotation = _annotation_from_dict(
        annotation_raw, task_type=task_type, image_id=image_id
    )
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=task_type,
        annotation=annotation,
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
        package_id=package_id,
        export_round=export_round,
    )


def _annotation_from_dict(
    raw: Any,
    *,
    task_type: TaskType,
    image_id: str,
) -> SegAnnotation | DetAnnotation | CapAnnotation:
    if not isinstance(raw, dict):
        raise ValueError(
            f"annotation must be an object (image_id={image_id!r})"
        )
    if task_type is TaskType.SEG:
        mask_ref = raw.get("mask_ref")
        if not isinstance(mask_ref, str) or not mask_ref.strip():
            raise ValueError(
                f"SEG annotation.mask_ref must be non-empty "
                f"(image_id={image_id!r})"
            )
        return SegAnnotation(mask_ref=mask_ref.strip())
    if task_type is TaskType.DET:
        bboxes_raw = raw.get("bboxes")
        if not isinstance(bboxes_raw, list):
            raise ValueError(
                f"DET annotation.bboxes must be a list (image_id={image_id!r})"
            )
        boxes: list[BBox] = []
        for box in bboxes_raw:
            if not isinstance(box, dict):
                raise ValueError(
                    f"DET bbox must be an object (image_id={image_id!r})"
                )
            try:
                boxes.append(
                    BBox(
                        x=float(box["x"]),
                        y=float(box["y"]),
                        width=float(box["width"]),
                        height=float(box["height"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"DET bbox missing numeric x/y/width/height "
                    f"(image_id={image_id!r})"
                ) from exc
        return DetAnnotation(bboxes=tuple(boxes))
    if task_type is TaskType.CAP:
        caption = raw.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError(
                f"CAP annotation.caption must be non-empty "
                f"(image_id={image_id!r})"
            )
        return CapAnnotation(caption=caption.strip())
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover


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
