"""Tests for common SEG current mask_ref path resolution.

V1 primary path: ``manual_masks/...`` under ``results/<batch>/seg/``.
``masks/...`` → ``prelabels/...`` remains historical compatibility until M5.4
(do not treat as V1 gold-standard layout).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.paths import prelabels_task_dir, results_task_dir
from mma.common.seg_mask_paths import (
    MANUAL_MASK_REL_DIR,
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


def test_prelabel_masks_resolves_under_prelabels(tmp_path: Path) -> None:
    """Historical compatibility: non-manual refs still resolve under prelabels (M5.4)."""

    resolved = resolve_current_seg_mask_path(
        "masks/img1.png",
        batch_id="batch1",
        data_root=tmp_path,
    )
    expected = (
        prelabels_task_dir("batch1", "seg", data_root=tmp_path) / "masks" / "img1.png"
    ).resolve()
    assert resolved == expected


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
