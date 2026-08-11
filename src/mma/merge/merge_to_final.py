"""Orchestrate multitask merge into ``final/<batch_id>/`` (T5.4).

Calls ``merge_multitask``, enriches ``image_path`` / ``diagnosis_text`` from
``processed/<batch_id>/manifest.json``, then ``write_final_manifest``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mma.common.models import MergedMultitaskRecord
from mma.common.paths import default_data_root, processed_batch_dir, validate_batch_id
from mma.merge.merge_multitask import merge_multitask
from mma.merge.write_final import write_final_manifest
from mma.packaging.split_task_packages import load_processed_items


def merge_to_final(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Merge three-task ``current/`` results and write ``final`` manifest.

    On failure before write, existing final manifest (if any) is left unchanged.
    Missing processed manifest or missing ``image_id`` in processed raises
    without writing.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    records = merge_multitask(cleaned, data_root=root)
    meta = _load_processed_image_meta(cleaned, data_root=root)
    enriched = _enrich_from_processed(records, meta)
    return write_final_manifest(enriched, batch_id=cleaned, data_root=root)


def _load_processed_image_meta(
    batch_id: str,
    *,
    data_root: Path,
) -> dict[str, tuple[str, str]]:
    """Return ``image_id -> (image_path, diagnosis_text)`` from processed."""

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


def _enrich_from_processed(
    records: Sequence[MergedMultitaskRecord],
    meta: dict[str, tuple[str, str]],
) -> tuple[MergedMultitaskRecord, ...]:
    enriched: list[MergedMultitaskRecord] = []
    for record in records:
        if record.image_id not in meta:
            raise ValueError(
                f"image_id={record.image_id!r} not found in processed manifest"
            )
        image_path, diagnosis_text = meta[record.image_id]
        enriched.append(
            MergedMultitaskRecord(
                image_id=record.image_id,
                seg=record.seg,
                det=record.det,
                cap=record.cap,
                image_path=image_path,
                diagnosis_text=diagnosis_text,
            )
        )
    return tuple(enriched)
