"""Write standardized processed batch directories (T1.3)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mma.common.io import write_json
from mma.common.models import ImageRecord
from mma.common.paths import processed_batch_dir, validate_batch_id
from mma.preprocess.assign_image_ids import assign_image_ids
from mma.preprocess.pair_images_excel import pair_images_with_excel


def _records_to_manifest_dict(
    records: Sequence[ImageRecord],
    batch_id: str,
) -> dict[str, object]:
    return {
        "batch_id": batch_id,
        "items": [
            {
                "image_id": record.image_id,
                "image_path": record.image_path,
                "diagnosis_text": record.diagnosis_text,
                "source_image_name": record.source_image_name,
            }
            for record in records
        ],
    }


def write_processed_manifest(
    records: Sequence[ImageRecord],
    processed_dir: Path | str,
) -> Path:
    """Write ``manifest.json`` under ``processed_dir`` (overwrite if exists).

    Does not copy image files. ``image_path`` values are written as stored
    on each ``ImageRecord`` (absolute paths from T1.1/T1.2).
    """

    if not records:
        raise ValueError("records must not be empty")

    batch_ids = {record.batch_id for record in records}
    if None in batch_ids:
        raise ValueError("all records must have a non-null batch_id")
    if len(batch_ids) != 1:
        raise ValueError(
            f"records span multiple batch_id values: {sorted(batch_ids)!r}"
        )

    only_batch_id = next(iter(batch_ids))
    assert only_batch_id is not None
    batch_id = validate_batch_id(only_batch_id)

    directory = Path(processed_dir)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    write_json(manifest_path, _records_to_manifest_dict(records, batch_id))
    return manifest_path


def build_processed_batch(
    batch_id: str,
    images_dir: Path | str,
    excel_path: Path | str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Pair images with Excel, assign image IDs, and write processed manifest.

    Returns the processed batch directory path.
    """

    cleaned_batch_id = validate_batch_id(batch_id)
    pairs = pair_images_with_excel(
        images_dir,
        excel_path,
        batch_id=cleaned_batch_id,
    )
    records = assign_image_ids(pairs, cleaned_batch_id)
    out_dir = processed_batch_dir(cleaned_batch_id, data_root=data_root)
    write_processed_manifest(records, out_dir)
    return out_dir
