"""Orchestrate multitask merge into a self-contained ``final/<batch_id>/`` (T5.4).

Calls ``merge_multitask``, copies images from task packages (fallback:
processed paths) into ``final/.../images/``, materializes SEG masks into
``final/.../masks/``, rewrites relative ``image_path`` / ``mask_ref``, then
``write_final_manifest``.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from mma.common.models import MergedMultitaskRecord, TaskType
from mma.common.paths import (
    default_data_root,
    final_images_dir,
    processed_batch_dir,
    validate_batch_id,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.merge.materialize_final_seg import (
    final_seg_mask_ref,
    materialize_final_seg_masks,
)
from mma.merge.merge_multitask import merge_multitask
from mma.merge.write_final import write_final_manifest
from mma.preprocess.load_processed import load_processed_items

FINAL_IMAGE_REL_DIR = "images"
_TASK_PACKAGE_LOOKUP_ORDER = (TaskType.SEG, TaskType.DET, TaskType.CAP)
_PACKAGE_IMAGE_MISS_MARKERS = (
    "images directory not found",
    "package image missing",
)


def final_image_path(image_id: str) -> str:
    """Return unified final image_path: ``images/{image_id}.jpg``."""

    cleaned = str(image_id).strip()
    if not cleaned:
        raise ValueError("image_id must be a non-empty string")
    return f"{FINAL_IMAGE_REL_DIR}/{cleaned}.jpg"


def merge_to_final(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Merge three-task ``current/`` results into a self-contained final dataset.

    On failure before write, existing final manifest (if any) is left unchanged.
    Missing processed manifest or missing ``image_id`` in processed raises
    without writing. Images are copied from task-package ``images/`` (seg then
    det then cap) with processed ``image_path`` as fallback, into
    ``images/{image_id}.jpg``. SEG masks go into ``masks/{image_id}.png``
    before the manifest is written. Manifest paths are relative to the final
    batch directory (no absolute paths).
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    records = merge_multitask(cleaned, data_root=root)
    meta = _load_processed_image_meta(cleaned, data_root=root)
    with_images = _copy_final_images(
        records,
        meta,
        batch_id=cleaned,
        data_root=root,
    )
    materialized = materialize_final_seg_masks(
        with_images,
        batch_id=cleaned,
        data_root=root,
    )
    assert_final_relative_paths(materialized)
    return write_final_manifest(materialized, batch_id=cleaned, data_root=root)


def _load_processed_image_meta(
    batch_id: str,
    *,
    data_root: Path,
) -> dict[str, tuple[str, str]]:
    """Return ``image_id -> (fallback image_path, diagnosis_text)`` from processed."""

    processed_dir = processed_batch_dir(batch_id, data_root=data_root)
    manifest_path = processed_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"processed manifest not found: {manifest_path}"
        )
    items = load_processed_items(processed_dir)
    indexed: dict[str, tuple[str, str]] = {}
    for item in items:
        if item.image_id in indexed:
            raise ValueError(
                f"duplicate image_id in processed manifest: {item.image_id!r}"
            )
        indexed[item.image_id] = (item.image_path, item.diagnosis_text)
    return indexed


def _try_resolve_task_package_image(
    batch_id: str,
    image_id: str,
    *,
    data_root: Path,
) -> Path | None:
    """Return the first task-package image, or ``None`` if none exist.

    Lookup order is SEG, DET, CAP. Missing directory / missing file is a miss;
    multiple matches for one task fail closed.
    """

    for task in _TASK_PACKAGE_LOOKUP_ORDER:
        try:
            return resolve_task_image_path(
                batch_id, task, image_id, data_root=data_root
            )
        except ValueError as exc:
            message = str(exc)
            if "multiple package images" in message:
                raise
            if any(marker in message for marker in _PACKAGE_IMAGE_MISS_MARKERS):
                continue
            raise
    return None


def _copy_final_images(
    records: Sequence[MergedMultitaskRecord],
    meta: dict[str, tuple[str, str]],
    *,
    batch_id: str,
    data_root: Path,
) -> tuple[MergedMultitaskRecord, ...]:
    """Copy source images into ``final/.../images/{image_id}.jpg``.

    Prefer ``task_packages/<batch>/{seg,det,cap}/images/``; fall back to the
    processed manifest ``image_path``. Target filename is always ``.jpg``
    regardless of source suffix.
    """

    images_dir = final_images_dir(batch_id, data_root=data_root)
    images_dir.mkdir(parents=True, exist_ok=True)
    out: list[MergedMultitaskRecord] = []
    for record in records:
        if record.image_id not in meta:
            raise ValueError(
                f"image_id={record.image_id!r} not found in processed manifest"
            )
        source_path_str, diagnosis_text = meta[record.image_id]
        source = _try_resolve_task_package_image(
            batch_id, record.image_id, data_root=data_root
        )
        if source is None:
            source = Path(source_path_str)
            if not source.is_file():
                raise FileNotFoundError(
                    f"source image not found for image_id={record.image_id!r}: "
                    f"not under task_packages/{batch_id}/{{seg,det,cap}}/images "
                    f"and processed path is missing: {source}"
                )
        dest = images_dir / f"{record.image_id}.jpg"
        shutil.copy2(source, dest)
        out.append(
            MergedMultitaskRecord(
                image_id=record.image_id,
                seg=record.seg,
                det=record.det,
                cap=record.cap,
                image_path=final_image_path(record.image_id),
                diagnosis_text=diagnosis_text,
            )
        )
    return tuple(out)


def assert_final_relative_paths(
    records: Sequence[MergedMultitaskRecord],
) -> None:
    """Require relative ``images/{id}.jpg`` and ``masks/{id}.png`` paths."""

    for record in records:
        expected_image = final_image_path(record.image_id)
        if record.image_path != expected_image:
            raise ValueError(
                f"final image_path contract failed for "
                f"image_id={record.image_id!r}: expected {expected_image!r}, "
                f"got {record.image_path!r}"
            )
        if record.image_path is None or Path(record.image_path).is_absolute():
            raise ValueError(
                f"final image_path must be relative "
                f"(image_id={record.image_id!r}, image_path={record.image_path!r})"
            )
        expected_mask = final_seg_mask_ref(record.image_id)
        if record.seg.mask_ref != expected_mask:
            raise ValueError(
                f"final mask_ref contract failed for "
                f"image_id={record.image_id!r}: expected {expected_mask!r}, "
                f"got {record.seg.mask_ref!r}"
            )
