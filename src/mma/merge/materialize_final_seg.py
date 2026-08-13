"""Materialize SEG masks into ``final/<batch>/final_assets/masks/`` (T5.4).

Copies current effective masks (manual or prelabel) into a single directory so
``final/.../manifest.json`` uses one ``mask_ref`` root. Does not modify
``prelabels/``, ``manual_masks/``, or ``current/``.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from mma.common.models import MergedMultitaskRecord, SegAnnotation, TaskType
from mma.common.paths import (
    default_data_root,
    final_assets_masks_dir,
    prelabels_task_dir,
    results_task_dir,
    validate_batch_id,
)
from mma.converters.seg_brush import MANUAL_MASK_REL_DIR

FINAL_SEG_MASK_REL_DIR = "final_assets/masks"
_FORBIDDEN_MASK_REF_MARKERS = ("manual_masks/", "prelabels/")


def final_seg_mask_ref(image_id: str) -> str:
    """Return unified final mask_ref: ``final_assets/masks/{image_id}.png``."""

    cleaned = str(image_id).strip()
    if not cleaned:
        raise ValueError("image_id must be a non-empty string")
    return f"{FINAL_SEG_MASK_REL_DIR}/{cleaned}.png"


def resolve_current_seg_mask_path(
    mask_ref: str,
    *,
    batch_id: str,
    data_root: Path | str | None = None,
) -> Path:
    """Resolve a ``current/`` SEG ``mask_ref`` to an absolute source file path.

    - ``manual_masks/...`` → ``results/<batch>/seg/manual_masks/...``
    - ``masks/...`` (and other relative refs) → ``prelabels/<batch>/seg/...``
    """

    cleaned_batch = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    ref = str(mask_ref).strip().replace("\\", "/")
    if not ref:
        raise ValueError("SEG mask_ref must be a non-empty string")
    if Path(ref).is_absolute() or ref.startswith("/") or ref.startswith(".."):
        raise ValueError(
            f"SEG mask_ref must be a safe relative path (image mask_ref={ref!r})"
        )

    if ref.startswith(f"{MANUAL_MASK_REL_DIR}/"):
        base = results_task_dir(cleaned_batch, TaskType.SEG, data_root=root)
        path = (base / ref).resolve()
        _assert_under_base(path, base.resolve(), mask_ref=ref)
        return path

    base = prelabels_task_dir(cleaned_batch, TaskType.SEG, data_root=root)
    path = (base / ref).resolve()
    _assert_under_base(path, base.resolve(), mask_ref=ref)
    return path


def materialize_final_seg_mask(
    *,
    image_id: str,
    seg: SegAnnotation,
    batch_id: str,
    data_root: Path | str | None = None,
) -> SegAnnotation:
    """Copy the current SEG mask into ``final_assets/masks/{image_id}.png``.

    Empty masks are copied as-is (not regenerated). Returns a new
    ``SegAnnotation`` with the unified ``mask_ref``.
    """

    if not isinstance(seg, SegAnnotation):
        raise TypeError(
            f"seg must be SegAnnotation, got {type(seg).__name__}"
        )

    cleaned_batch = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    source = resolve_current_seg_mask_path(
        seg.mask_ref,
        batch_id=cleaned_batch,
        data_root=root,
    )
    if not source.is_file():
        raise FileNotFoundError(
            f"SEG mask file not found for image_id={image_id!r}: {source} "
            f"(mask_ref={seg.mask_ref!r})"
        )

    dest_dir = final_assets_masks_dir(cleaned_batch, data_root=root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{str(image_id).strip()}.png"
    shutil.copy2(source, dest)
    return SegAnnotation(mask_ref=final_seg_mask_ref(image_id))


def materialize_final_seg_masks(
    records: Sequence[MergedMultitaskRecord],
    *,
    batch_id: str,
    data_root: Path | str | None = None,
) -> tuple[MergedMultitaskRecord, ...]:
    """Materialize every record's SEG mask; return records with unified refs."""

    cleaned_batch = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    out: list[MergedMultitaskRecord] = []
    for record in records:
        new_seg = materialize_final_seg_mask(
            image_id=record.image_id,
            seg=record.seg,
            batch_id=cleaned_batch,
            data_root=root,
        )
        out.append(
            MergedMultitaskRecord(
                image_id=record.image_id,
                seg=new_seg,
                det=record.det,
                cap=record.cap,
                image_path=record.image_path,
                diagnosis_text=record.diagnosis_text,
            )
        )
    assert_final_seg_mask_contract(out)
    return tuple(out)


def assert_final_seg_mask_contract(
    records: Sequence[MergedMultitaskRecord],
) -> None:
    """Require every ``seg.mask_ref`` to be ``final_assets/masks/{image_id}.png``.

    Forbids bare ``masks/``, ``manual_masks/``, and ``prelabels/`` references.
    """

    for record in records:
        expected = final_seg_mask_ref(record.image_id)
        ref = record.seg.mask_ref
        if ref != expected:
            raise ValueError(
                f"final SEG mask_ref contract failed for "
                f"image_id={record.image_id!r}: expected {expected!r}, "
                f"got {ref!r}"
            )
        normalized = ref.replace("\\", "/")
        if normalized.startswith("masks/") or any(
            marker in normalized for marker in _FORBIDDEN_MASK_REF_MARKERS
        ):
            raise ValueError(
                f"final SEG mask_ref must not use prelabel/manual roots "
                f"(image_id={record.image_id!r}, mask_ref={ref!r})"
            )


def _assert_under_base(path: Path, base: Path, *, mask_ref: str) -> None:
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"SEG mask_ref escapes expected root: mask_ref={mask_ref!r}, "
            f"resolved={path}, base={base}"
        ) from exc
