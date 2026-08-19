"""Serialize / deserialize ``TaskAnnotationResult`` for ``current/annotations.json``.

Format matches T4.4: a JSON array of objects with the same fields as
``TaskAnnotationResult``. No separate business schema.
"""

from __future__ import annotations

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
from mma.common.seg_mask_paths import compute_has_foreground

ANNOTATIONS_JSON_NAME = "annotations.json"


def task_annotation_result_to_dict(item: TaskAnnotationResult) -> dict[str, Any]:
    """Convert one ``TaskAnnotationResult`` to a JSON-compatible dict."""

    return {
        "image_id": item.image_id,
        "task_type": item.task_type.value,
        "annotation": _annotation_to_dict(item),
        "human_confirmed": item.human_confirmed,
        "needs_rework": item.needs_rework,
        "package_id": item.package_id,
        "export_round": item.export_round,
    }


def task_annotation_result_from_dict(
    raw: Any,
    *,
    index: int,
    mask_root: Path | str | None = None,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
) -> TaskAnnotationResult:
    """Parse one JSON object into ``TaskAnnotationResult``."""

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
        annotation_raw,
        task_type=task_type,
        image_id=image_id,
        mask_root=mask_root,
        batch_id=batch_id,
        data_root=data_root,
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


def parse_annotations_payload(
    payload: Any,
    *,
    task_type: TaskType,
    source: str,
    mask_root: Path | str | None = None,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Parse an in-memory annotations JSON payload (must be a list)."""

    if not isinstance(payload, list):
        raise ValueError(
            f"current annotations.json must be a JSON array of "
            f"TaskAnnotationResult objects: {source}"
        )
    items: list[TaskAnnotationResult] = []
    seen: set[str] = set()
    for index, raw in enumerate(payload):
        item = task_annotation_result_from_dict(
            raw,
            index=index,
            mask_root=mask_root,
            batch_id=batch_id,
            data_root=data_root,
        )
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
    return tuple(items)


def read_annotations_json(
    path: Path | str,
    *,
    task_type: TaskType,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Read ``annotations.json`` from ``path`` (file must exist).

    SEG ``has_foreground`` is recomputed from mask pixels. ``mask_root`` is
    the task directory (parent of ``current/`` / ``rework/``).
    """

    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"json file not found: {target}")
    payload = read_json(target)
    mask_root = target.resolve().parent.parent
    return parse_annotations_payload(
        payload,
        task_type=task_type,
        source=str(target),
        mask_root=mask_root,
        batch_id=batch_id,
        data_root=data_root,
    )


def _annotation_to_dict(item: TaskAnnotationResult) -> dict[str, Any]:
    annotation = item.annotation
    if isinstance(annotation, SegAnnotation):
        return {
            "mask_ref": annotation.mask_ref,
            "has_foreground": annotation.has_foreground,
        }
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


def _annotation_from_dict(
    raw: Any,
    *,
    task_type: TaskType,
    image_id: str,
    mask_root: Path | str | None = None,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
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
        if "has_foreground" in raw and not isinstance(
            raw["has_foreground"], bool
        ):
            raise ValueError(
                f"SEG annotation.has_foreground must be bool "
                f"(image_id={image_id!r})"
            )
        cleaned_ref = mask_ref.strip()
        return SegAnnotation(
            mask_ref=cleaned_ref,
            has_foreground=compute_has_foreground(
                cleaned_ref,
                mask_root=mask_root,
                batch_id=batch_id,
                data_root=data_root,
            ),
        )
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
        if not isinstance(caption, str):
            raise ValueError(
                f"CAP annotation.caption must be a string "
                f"(image_id={image_id!r})"
            )
        # Empty string is a valid human-clear state (not "missing").
        return CapAnnotation(caption=caption.strip())
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover
