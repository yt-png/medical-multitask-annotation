"""Merge SEG/DET/CAP current results by image_id (T5.2).

Calls ``validate_ready`` first. Returns in-memory ``MergedMultitaskRecord``
tuples only; does not write ``final/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import default_data_root, validate_batch_id
from mma.exporters.load_current import load_current
from mma.merge.validate_ready import validate_ready

_T = TypeVar("_T")


def merge_multitask(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> tuple[MergedMultitaskRecord, ...]:
    """Align SEG/DET/CAP current annotations into multitask records.

    Order follows the SEG ``current/`` list. ``image_path`` and
    ``diagnosis_text`` are left as ``None``.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    validate_ready(cleaned, data_root=root)

    seg_items = load_current(cleaned, TaskType.SEG, data_root=root)
    det_items = load_current(cleaned, TaskType.DET, data_root=root)
    cap_items = load_current(cleaned, TaskType.CAP, data_root=root)

    det_by_id = _index_by_image_id(det_items, task_label="DET")
    cap_by_id = _index_by_image_id(cap_items, task_label="CAP")

    merged: list[MergedMultitaskRecord] = []
    for seg_item in seg_items:
        image_id = seg_item.image_id
        if image_id not in det_by_id:
            raise ValueError(
                f"missing DET annotation for image_id={image_id!r}"
            )
        if image_id not in cap_by_id:
            raise ValueError(
                f"missing CAP annotation for image_id={image_id!r}"
            )

        seg = _require_annotation(
            seg_item,
            SegAnnotation,
            image_id=image_id,
            task_label="SEG",
        )
        det = _require_annotation(
            det_by_id[image_id],
            DetAnnotation,
            image_id=image_id,
            task_label="DET",
        )
        cap = _require_annotation(
            cap_by_id[image_id],
            CapAnnotation,
            image_id=image_id,
            task_label="CAP",
        )
        merged.append(
            MergedMultitaskRecord(
                image_id=image_id,
                seg=seg,
                det=det,
                cap=cap,
                image_path=None,
                diagnosis_text=None,
            )
        )
    return tuple(merged)


def _index_by_image_id(
    items: Sequence[TaskAnnotationResult],
    *,
    task_label: str,
) -> dict[str, TaskAnnotationResult]:
    indexed: dict[str, TaskAnnotationResult] = {}
    for item in items:
        if item.image_id in indexed:
            raise ValueError(
                f"duplicate image_id={item.image_id!r} in {task_label} current"
            )
        indexed[item.image_id] = item
    return indexed


def _require_annotation(
    item: TaskAnnotationResult,
    expected: type[_T],
    *,
    image_id: str,
    task_label: str,
) -> _T:
    annotation = item.annotation
    if not isinstance(annotation, expected):
        raise ValueError(
            f"{task_label} annotation type mismatch for image_id={image_id!r}: "
            f"expected {expected.__name__}, got {type(annotation).__name__}"
        )
    return annotation
