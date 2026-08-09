"""Split a processed batch into three full task package image trees (T1.4).

Does not write task-package ``manifest.json`` or assign ``package_id`` (T1.5).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from mma.common.io import read_json
from mma.common.models import ImageRecord, SampleItem, TaskType
from mma.common.paths import (
    processed_batch_dir,
    task_package_dir,
    validate_batch_id,
)

_TASK_TYPES = (TaskType.SEG, TaskType.DET, TaskType.CAP)


def _package_image_filename(image_id: str, source_path: Path) -> str:
    """Build ``{image_id}{ext}`` using the source file suffix (lowercased)."""

    suffix = source_path.suffix.lower()
    if not suffix:
        raise ValueError(f"source image has no extension: {source_path}")
    return f"{image_id}{suffix}"


def load_processed_items(processed_dir: Path | str) -> tuple[ImageRecord, ...]:
    """Load ``ImageRecord`` rows from ``processed_dir/manifest.json``."""

    directory = Path(processed_dir)
    manifest_path = directory / "manifest.json"
    payload = read_json(manifest_path)

    if not isinstance(payload, dict):
        raise ValueError(f"processed manifest must be an object: {manifest_path}")

    batch_id = payload.get("batch_id")
    if not batch_id or not str(batch_id).strip():
        raise ValueError(f"processed manifest missing batch_id: {manifest_path}")
    batch_id = validate_batch_id(str(batch_id))

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"processed manifest has no items: {manifest_path}")

    records: list[ImageRecord] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"processed manifest item {index} must be an object")
        try:
            image_id = str(item["image_id"]).strip()
            image_path = str(item["image_path"]).strip()
            diagnosis_text = str(item["diagnosis_text"]).strip()
        except KeyError as exc:
            raise ValueError(
                f"processed manifest item {index} missing field {exc.args[0]!r}"
            ) from exc

        if not image_id or not image_path or not diagnosis_text:
            raise ValueError(
                f"processed manifest item {index} has empty required fields"
            )

        source_image_name = item.get("source_image_name")
        if source_image_name is None or str(source_image_name).strip() == "":
            source_image_name = Path(image_path).name
        else:
            source_image_name = str(source_image_name)

        records.append(
            ImageRecord(
                image_id=image_id,
                image_path=image_path,
                diagnosis_text=diagnosis_text,
                batch_id=batch_id,
                source_image_name=source_image_name,
            )
        )

    return tuple(records)


def _copy_task_images(
    records: tuple[ImageRecord, ...],
    package_dir: Path,
) -> tuple[SampleItem, ...]:
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

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
