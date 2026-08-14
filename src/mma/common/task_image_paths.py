"""Resolve task-package image file paths (shared by importers / exporters).

Looks up ``task_packages/<batch>/<task>/images/{image_id}.*``.
Does not build Label Studio URLs or read image pixels.
"""

from __future__ import annotations

from pathlib import Path

from mma.common.models import TaskType
from mma.common.paths import task_package_dir

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".JPG", ".JPEG")


def resolve_task_image_path(
    batch_id: str,
    task: str | TaskType,
    image_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Resolve ``task_packages/.../images/{image_id}.*`` under ``data_root``."""

    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    images_dir = package_dir / "images"
    if not images_dir.is_dir():
        raise ValueError(
            f"task package images directory not found: {images_dir} "
            f"(batch_id={batch_id!r}, image_id={image_id!r})"
        )

    matches = sorted(
        p
        for p in images_dir.iterdir()
        if p.is_file() and p.stem == image_id and p.suffix in _IMAGE_SUFFIXES
    )
    if not matches:
        raise ValueError(
            f"package image missing for image_id={image_id!r}: "
            f"expected under {images_dir}"
        )
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise ValueError(
            f"multiple package images for image_id={image_id!r}: {names}"
        )
    return matches[0].resolve()
