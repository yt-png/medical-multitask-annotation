"""Tests for common task-package image path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.paths import task_package_dir
from mma.common.task_image_paths import resolve_task_image_path


def _place_image(
    tmp_path: Path,
    *,
    batch_id: str,
    task: str,
    image_id: str,
    suffix: str = ".jpg",
) -> Path:
    images_dir = task_package_dir(batch_id, task, data_root=tmp_path) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / f"{image_id}{suffix}"
    path.write_bytes(b"fake-image")
    return path.resolve()


def test_resolves_jpg_under_task_packages(tmp_path: Path) -> None:
    expected = _place_image(
        tmp_path, batch_id="batch1", task="det", image_id="batch1__000001"
    )
    resolved = resolve_task_image_path(
        "batch1",
        "det",
        "batch1__000001",
        data_root=tmp_path,
    )
    assert resolved == expected


def test_resolves_jpeg_suffix(tmp_path: Path) -> None:
    expected = _place_image(
        tmp_path,
        batch_id="batch1",
        task="seg",
        image_id="img1",
        suffix=".jpeg",
    )
    resolved = resolve_task_image_path(
        "batch1",
        "seg",
        "img1",
        data_root=tmp_path,
    )
    assert resolved == expected


def test_missing_images_dir_raises(tmp_path: Path) -> None:
    task_package_dir("batch1", "cap", data_root=tmp_path).mkdir(parents=True)
    with pytest.raises(ValueError, match="images directory not found"):
        resolve_task_image_path(
            "batch1",
            "cap",
            "img1",
            data_root=tmp_path,
        )


def test_missing_image_file_raises(tmp_path: Path) -> None:
    images_dir = task_package_dir("batch1", "det", data_root=tmp_path) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="package image missing"):
        resolve_task_image_path(
            "batch1",
            "det",
            "missing_id",
            data_root=tmp_path,
        )


def test_multiple_matches_raises(tmp_path: Path) -> None:
    _place_image(
        tmp_path, batch_id="batch1", task="det", image_id="dup", suffix=".jpg"
    )
    _place_image(
        tmp_path, batch_id="batch1", task="det", image_id="dup", suffix=".jpeg"
    )
    with pytest.raises(ValueError, match="multiple package images"):
        resolve_task_image_path(
            "batch1",
            "det",
            "dup",
            data_root=tmp_path,
        )
