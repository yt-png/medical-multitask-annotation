"""Tests for SEG mask ↔ Label Studio polygonlabels conversion."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mma.common.models import TaskType
from mma.converters import (
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
    build_seg_polygon_results,
    item_to_ls_task,
)
from mma.converters.seg_polygon import (
    binary_mask_to_polygon_points,
    mask_iou,
    polygon_results_to_binary_mask,
    polygons_to_binary_mask,
    write_manual_mask_from_polygon_results,
)
from mma.formats.legacy_prelabel import PrelabelItem, SCHEMA_VERSION, SegPrelabelPayload


def _save_l_mask(path: Path, pixels: list[list[int]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    img = Image.new("L", (width, height))
    flat = [255 if cell else 0 for row in pixels for cell in row]
    img.putdata(flat)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _seg_item(mask_ref: str = "masks/a.png") -> PrelabelItem:
    return PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="demo_batch",
        package_id="demo_batch__seg",
        task_type=TaskType.SEG,
        image_id="demo_batch__000001",
        diagnosis_text="diag",
        payload=SegPrelabelPayload(mask_ref=mask_ref),
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


def test_build_seg_polygon_results(tmp_path: Path) -> None:
    _save_l_mask(
        tmp_path / "masks" / "a.png",
        [
            [1, 1, 0, 0],
            [1, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 0, 1],
        ],
    )
    results = build_seg_polygon_results(_seg_item(), mask_root=tmp_path)
    assert len(results) == 2
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]
    for result in results:
        assert result["type"] == "polygonlabels"
        assert result["from_name"] == spec["from_name"]
        assert result["to_name"] == spec["to_name"]
        assert "points" in result["value"]
        assert result["value"]["polygonlabels"] == list(spec["labels"])
        assert len(result["value"]["points"]) >= 3


def test_item_to_ls_task_default_polygon_prefill(tmp_path: Path) -> None:
    _save_l_mask(
        tmp_path / "masks" / "a.png",
        [
            [1, 1, 0],
            [1, 1, 0],
            [0, 0, 0],
        ],
    )
    task = item_to_ls_task(_seg_item(), mask_root=tmp_path)
    results = task["predictions"][0]["result"]
    assert len(results) >= 1
    assert results[0]["type"] == "polygonlabels"


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


def test_build_size_mismatch_raises(tmp_path: Path) -> None:
    _save_l_mask(tmp_path / "masks" / "a.png", [[1, 1], [1, 1]])
    with pytest.raises(ValueError, match="does not match image_metadata"):
        build_seg_polygon_results(
            _seg_item(),
            mask_root=tmp_path,
            image_metadata=ImageMetadata(width=10, height=10),
        )
