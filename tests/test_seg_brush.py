"""Tests for SEG mask → LS brush geometry (T3.1b decode / RLE)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.converters.seg_brush import (
    brush_results_to_binary_mask,
    find_connected_components,
    load_foreground_mask,
    ls_rle_to_binary_mask,
    mask_to_ls_rle,
    union_binary_masks,
)


def _save_l_mask(path: Path, pixels: list[list[int]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    img = Image.new("L", (width, height))
    flat = [255 if cell else 0 for row in pixels for cell in row]
    img.putdata(flat)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def test_load_foreground_l_mode_and_threshold(tmp_path: Path) -> None:
    path = tmp_path / "m.png"
    _save_l_mask(path, [[0, 10], [0, 0]])
    binary, width, height = load_foreground_mask(path)
    assert (width, height) == (2, 2)
    assert binary == [[0, 1], [0, 0]]


def test_load_rgba_uses_alpha(tmp_path: Path) -> None:
    path = tmp_path / "rgba.png"
    img = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    img.putpixel((1, 0), (0, 0, 0, 200))
    img.save(path)
    binary, width, height = load_foreground_mask(path)
    assert (width, height) == (2, 1)
    assert binary == [[0, 1]]


def test_two_disconnected_blobs_yield_two_components() -> None:
    binary = [
        [1, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 0, 1],
    ]
    comps = find_connected_components(binary)
    assert len(comps) == 2
    # Sorted by centroid: top-left blob first
    assert comps[0][0][0] == 1
    assert comps[1][2][3] == 1


def test_diagonal_touch_is_one_component_8conn() -> None:
    binary = [
        [1, 0],
        [0, 1],
    ]
    comps = find_connected_components(binary)
    assert len(comps) == 1
    assert comps[0] == binary


def test_empty_mask_yields_no_components() -> None:
    assert find_connected_components([[0, 0], [0, 0]]) == []


def test_mask_to_ls_rle_non_empty_for_blob() -> None:
    binary = [[0, 1], [0, 0]]
    rle = mask_to_ls_rle(binary)
    assert isinstance(rle, list)
    assert rle
    assert all(isinstance(x, int) for x in rle)


def test_multivalue_pixels_same_class(tmp_path: Path) -> None:
    path = tmp_path / "masks" / "a.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("L", (3, 1))
    img.putpixel((0, 0), 1)
    img.putpixel((1, 0), 0)
    img.putpixel((2, 0), 255)
    img.save(path)
    binary, _, _ = load_foreground_mask(path)
    assert binary == [[1, 0, 1]]
    comps = find_connected_components(binary)
    assert len(comps) == 2


def test_encode_decode_rle_roundtrip() -> None:
    binary = [
        [0, 1, 0, 0],
        [0, 1, 0, 1],
        [0, 0, 0, 1],
        [1, 0, 0, 0],
    ]
    rle = mask_to_ls_rle(binary)
    decoded = ls_rle_to_binary_mask(rle, width=4, height=4)
    assert decoded == binary


def test_union_binary_masks_or() -> None:
    mask_a = [
        [1, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    mask_b = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 1],
    ]
    assert union_binary_masks([mask_a, mask_b]) == [
        [1, 0, 0],
        [0, 0, 0],
        [0, 0, 1],
    ]


def test_multiple_brush_rle_decode_union() -> None:
    mask_a = [
        [1, 0],
        [0, 0],
    ]
    mask_b = [
        [0, 0],
        [0, 1],
    ]
    entries = [
        {
            "original_width": 2,
            "original_height": 2,
            "value": {"format": "rle", "rle": mask_to_ls_rle(mask_a)},
        },
        {
            "original_width": 2,
            "original_height": 2,
            "value": {"format": "rle", "rle": mask_to_ls_rle(mask_b)},
        },
    ]
    unioned = brush_results_to_binary_mask(entries, image_id="img-x")
    assert unioned == [
        [1, 0],
        [0, 1],
    ]
