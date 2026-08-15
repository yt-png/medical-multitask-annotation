"""Split a processed batch into three full task package image trees (T1.4).

Does not write task-package ``manifest.json`` or assign ``package_id`` (T1.5).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from mma.common.models import ImageRecord, SampleItem, TaskType
from mma.common.paths import (
    processed_batch_dir,
    task_package_dir,
    validate_batch_id,
)
from mma.preprocess.load_processed import load_processed_items

_TASK_TYPES = (TaskType.SEG, TaskType.DET, TaskType.CAP)


def _package_image_filename(image_id: str, source_path: Path) -> str:
    """Build ``{image_id}{ext}`` using the source file suffix (lowercased)."""

    suffix = source_path.suffix.lower()
    if not suffix:
        raise ValueError(f"source image has no extension: {source_path}")
    return f"{image_id}{suffix}"


def _expected_image_filenames(records: tuple[ImageRecord, ...]) -> set[str]:
    """Return filenames that this run will write under ``images/``."""

    return {
        _package_image_filename(record.image_id, Path(record.image_path))
        for record in records
    }


def _remove_unlisted_images(images_dir: Path, expected_names: set[str]) -> None:
    """Delete files in ``images_dir`` that are not in ``expected_names``.

    Subdirectories are rejected (``ValueError``). Expected files are left for
    subsequent ``copy2`` overwrite. Missing directory is a no-op for callers
    that have not created it yet; callers normally ``mkdir`` first.
    """

    if not images_dir.is_dir():
        return

    for entry in images_dir.iterdir():
        if entry.is_dir():
            raise ValueError(
                f"unexpected subdirectory in package images directory: {entry}"
            )
        if entry.is_file() and entry.name not in expected_names:
            entry.unlink()


def _copy_task_images(
    records: tuple[ImageRecord, ...],
    package_dir: Path,
) -> tuple[SampleItem, ...]:
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    expected = _expected_image_filenames(records)
    _remove_unlisted_images(images_dir, expected)

    samples: list[SampleItem] = []
    for record in records:
        source = Path(record.image_path)
        if not source.is_file():
            raise ValueError(
                f"source image not found for image_id={record.image_id!r}: "
                f"{source}"
            )

        filename = _package_image_filename(record.image_id, source)
        destination = images_dir / filename
        shutil.copy2(source, destination)

        samples.append(
            SampleItem(
                image_id=record.image_id,
                image_path=f"images/{filename}",
                diagnosis_text=record.diagnosis_text,
            )
        )

    return tuple(samples)


def split_task_packages(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> dict[TaskType, tuple[SampleItem, ...]]:
    """Copy full image sets into SEG/DET/CAP package ``images/`` directories.

    Re-runs align each task ``images/`` to the current processed list: files
    not in the expected filename set are removed before copy.

    Returns per-task ``SampleItem`` tuples with package-relative ``image_path``.
    Does not write JSON or construct ``TaskPackage``.
    """

    cleaned = validate_batch_id(batch_id)
    processed_dir = processed_batch_dir(cleaned, data_root=data_root)
    if not processed_dir.is_dir():
        raise FileNotFoundError(f"processed batch directory not found: {processed_dir}")

    records = load_processed_items(processed_dir)
    result: dict[TaskType, tuple[SampleItem, ...]] = {}

    for task_type in _TASK_TYPES:
        package_dir = task_package_dir(cleaned, task_type, data_root=data_root)
        result[task_type] = _copy_task_images(records, package_dir)

    return result
