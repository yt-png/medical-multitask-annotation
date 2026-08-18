"""Tests for SEG mask ↔ Label Studio polygonlabels conversion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from mma.converters.seg_polygon import (
    binary_mask_to_polygon_points,
    mask_iou,
    polygon_results_to_binary_mask,
    polygons_to_binary_mask,
    write_manual_mask_from_polygon_results,
)


def test_polygons_to_binary_mask_fillpoly_or_union() -> None:
    poly_a = [[10.0, 10.0], [40.0, 10.0], [40.0, 40.0], [10.0, 40.0]]
    poly_b = [[60.0, 60.0], [90.0, 60.0], [90.0, 90.0], [60.0, 90.0]]
    mask = polygons_to_binary_mask([poly_a, poly_b], width=100, height=100)
    assert mask.dtype == np.uint8
    assert mask.shape == (100, 100)
    assert mask[20, 20] == 1
    assert mask[70, 70] == 1
    assert mask[50, 50] == 0


def test_polygon_results_to_binary_mask() -> None:
    entries = [
        {
            "original_width": 50,
            "original_height": 50,
            "value": {
                "points": [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]],
                "polygonlabels": ["lesion"],
            },
        }
    ]
    mask = polygon_results_to_binary_mask(entries, image_id="img")
    assert mask.shape == (50, 50)
    assert int(mask.sum()) == 50 * 50


def test_mask_to_polygon_and_roundtrip_iou() -> None:
    # Solid rectangle with margin so contour approx is stable.
    mask = np.zeros((80, 80), dtype=np.uint8)
    mask[20:60, 15:55] = 1
    polygons = binary_mask_to_polygon_points(mask)
    assert len(polygons) == 1
    assert len(polygons[0]) >= 3
    rebuilt = polygons_to_binary_mask(polygons, width=80, height=80)
    assert mask_iou(mask, rebuilt) >= 0.9


def test_mask_to_polygon_emits_bbox_for_tiny_blob() -> None:
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2, 3] = 1
    polygons = binary_mask_to_polygon_points(mask)
    assert len(polygons) == 1
    assert len(polygons[0]) >= 3
    rebuilt = polygons_to_binary_mask(polygons, width=8, height=8)
    assert rebuilt.sum() >= 1


def test_write_manual_mask_from_polygon_results(tmp_path: Path) -> None:
    entries = [
        {
            "original_width": 32,
            "original_height": 32,
            "type": "polygonlabels",
            "value": {
                "points": [[25.0, 25.0], [75.0, 25.0], [75.0, 75.0], [25.0, 75.0]],
                "polygonlabels": ["lesion"],
            },
        }
    ]
    ref = write_manual_mask_from_polygon_results(
        entries,
        image_id="img-poly",
        manual_mask_dir=tmp_path,
    )
    assert ref == "manual_masks/img-poly_manual.png"
    path = tmp_path / "img-poly_manual.png"
    assert path.is_file()
    with Image.open(path) as img:
        arr = np.asarray(img.convert("L"))
    assert (arr > 0).sum() > 0
