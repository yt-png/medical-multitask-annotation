"""Tests for common SEG current mask_ref path resolution.

V1: only ``manual_masks/...`` under ``results/<batch>/seg/``.
Legacy ``masks/...`` → ``prelabels/...`` is rejected (M5.4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.paths import results_task_dir
from mma.common.seg_mask_paths import (
    MANUAL_MASK_REL_DIR,
    compute_has_foreground,
    resolve_current_seg_mask_path,
)


def test_manual_masks_resolves_under_results(tmp_path: Path) -> None:
    """V1 primary: human manual mask under results/.../manual_masks/."""

    resolved = resolve_current_seg_mask_path(
        f"{MANUAL_MASK_REL_DIR}/img1_manual.png",
        batch_id="batch1",
        data_root=tmp_path,
    )
    expected = (
        results_task_dir("batch1", "seg", data_root=tmp_path)
        / MANUAL_MASK_REL_DIR
        / "img1_manual.png"
    ).resolve()
    assert resolved == expected


def test_legacy_prelabel_masks_ref_is_rejected(tmp_path: Path) -> None:
    """Legacy ``masks/...`` must not resolve under prelabels (M5.4)."""

    with pytest.raises(ValueError, match="manual_masks|not a V1 fallback"):
        resolve_current_seg_mask_path(
            "masks/img1.png",
            batch_id="batch1",
            data_root=tmp_path,
        )


def test_rejects_empty_mask_ref(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        resolve_current_seg_mask_path(
            "",
            batch_id="batch1",
            data_root=tmp_path,
        )


def test_rejects_absolute_mask_ref(tmp_path: Path) -> None:
    absolute = str((tmp_path / "abs.png").resolve())
    with pytest.raises(ValueError, match="safe relative path"):
        resolve_current_seg_mask_path(
            absolute,
            batch_id="batch1",
            data_root=tmp_path,
        )


def test_rejects_parent_traversal_prefix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="safe relative path"):
        resolve_current_seg_mask_path(
            "../outside.png",
            batch_id="batch1",
            data_root=tmp_path,
        )


def test_rejects_escape_via_dotdot_segment(tmp_path: Path) -> None:
    # One ``..`` stays under seg/; two ``..`` escapes results/<batch>/seg/.
    with pytest.raises(ValueError, match="escapes expected root"):
        resolve_current_seg_mask_path(
            f"{MANUAL_MASK_REL_DIR}/../../outside.png",
            batch_id="batch1",
            data_root=tmp_path,
        )


def _write_l_png(path: Path, pixels: list[list[int]]) -> None:
    from PIL import Image

    height = len(pixels)
    width = len(pixels[0])
    image = Image.new("L", (width, height), 0)
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            image.putpixel((x, y), value)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def test_compute_has_foreground_empty_mask_ref() -> None:
    assert compute_has_foreground("") is False
    assert compute_has_foreground("   ") is False
    assert compute_has_foreground(None) is False


def test_compute_has_foreground_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.png"
    assert (
        compute_has_foreground("manual_masks/nope.png", mask_path=missing)
        is False
    )


def test_compute_has_foreground_all_black(tmp_path: Path) -> None:
    path = tmp_path / "black.png"
    _write_l_png(path, [[0, 0], [0, 0]])
    assert compute_has_foreground("black.png", mask_path=path) is False


def test_compute_has_foreground_white_pixel(tmp_path: Path) -> None:
    path = tmp_path / "fg.png"
    _write_l_png(path, [[0, 0], [0, 255]])
    assert compute_has_foreground("fg.png", mask_path=path) is True


def test_json_has_foreground_false_does_not_override_mask_pixels(
    tmp_path: Path,
) -> None:
    from mma.common.io import write_json
    from mma.common.models import TaskType
    from mma.common.paths import results_current_dir, results_manual_masks_dir
    from mma.exporters import load_current

    mask_dir = results_manual_masks_dir("b1", data_root=tmp_path)
    mask_file = mask_dir / "xxx_manual.png"
    _write_l_png(mask_file, [[0, 255], [0, 0]])
    path = (
        results_current_dir("b1", TaskType.SEG, data_root=tmp_path)
        / "annotations.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        path,
        [
            {
                "image_id": "img-x",
                "task_type": "SEG",
                "annotation": {
                    "mask_ref": "manual_masks/xxx_manual.png",
                    "has_foreground": False,
                },
                "human_confirmed": True,
                "needs_rework": False,
                "package_id": None,
                "export_round": None,
            }
        ],
    )
    loaded = load_current("b1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.has_foreground is True
