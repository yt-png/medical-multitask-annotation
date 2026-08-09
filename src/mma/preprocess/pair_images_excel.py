"""Pair directory images with Excel diagnosis rows (T1.1)."""

from __future__ import annotations

from pathlib import Path

from mma.common.io import list_image_files, read_diagnosis_excel
from mma.common.models import ImageTextPair


def _normalize_key(name: str) -> str:
    """Normalize a full filename for matching: strip + case-fold."""

    return name.strip().casefold()


def pair_images_with_excel(
    images_dir: Path | str,
    excel_path: Path | str,
    batch_id: str | None = None,
) -> tuple[ImageTextPair, ...]:
    """Build one-to-one image/text pairs from a jpg directory and Excel file.

    Matching uses the full filename (including extension), after strip and
    case-insensitive normalization. Any mismatch, duplicate key, or empty
    diagnosis text fails the entire batch.
    """

    image_paths = list_image_files(images_dir)
    excel_rows = read_diagnosis_excel(excel_path)

    images_by_key: dict[str, Path] = {}
    for path in image_paths:
        key = _normalize_key(path.name)
        if key in images_by_key:
            raise ValueError(
                f"duplicate image filename after normalization: {path.name!r}"
            )
        images_by_key[key] = path

    excel_by_key: dict[str, tuple[str, str]] = {}
    for image_name, diagnosis_text in excel_rows:
        key = _normalize_key(image_name)
        if key in excel_by_key:
            raise ValueError(
                f"duplicate image_name in excel after normalization: {image_name!r}"
            )
        excel_by_key[key] = (image_name, diagnosis_text)

    image_keys = set(images_by_key)
    excel_keys = set(excel_by_key)

    missing_in_excel = sorted(image_keys - excel_keys)
    missing_in_images = sorted(excel_keys - image_keys)
    if missing_in_excel or missing_in_images:
        parts: list[str] = []
        if missing_in_excel:
            names = [images_by_key[k].name for k in missing_in_excel]
            parts.append(f"images without excel rows: {names}")
        if missing_in_images:
            names = [excel_by_key[k][0] for k in missing_in_images]
            parts.append(f"excel rows without images: {names}")
        raise ValueError("; ".join(parts))

    pairs = [
        ImageTextPair(
            image_path=str(images_by_key[key]),
            diagnosis_text=excel_by_key[key][1],
            source_image_name=images_by_key[key].name,
            batch_id=batch_id,
        )
        for key in sorted(image_keys)
    ]
    return tuple(pairs)
