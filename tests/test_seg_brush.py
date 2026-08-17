"""Tests for SEG mask → LS brush prefill (T3.1b)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.models import TaskType
from mma.converters import (
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
    build_seg_brush_results,
    document_to_ls_tasks,
    item_to_ls_task,
)
from mma.converters.seg_brush import (
    find_connected_components,
    load_foreground_mask,
    ls_rle_to_binary_mask,
    mask_to_ls_rle,
    union_binary_masks,
)
from mma.formats.legacy_prelabel import (
    PrelabelDocument,
    PrelabelItem,
    SCHEMA_VERSION,
    SegPrelabelPayload,
)


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


def test_build_seg_brush_results_writes_spec_fields(tmp_path: Path) -> None:
    mask_path = tmp_path / "masks" / "a.png"
    _save_l_mask(
        mask_path,
        [
            [1, 0, 0],
            [0, 0, 0],
            [0, 0, 1],
        ],
    )
    item = _seg_item("masks/a.png")
    results = build_seg_brush_results(item, mask_root=tmp_path)
    assert len(results) == 2
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]
    for result in results:
        assert result["from_name"] == spec["from_name"]
        assert result["to_name"] == spec["to_name"]
        assert result["type"] == "brushlabels"
        assert result["original_width"] == 3
        assert result["original_height"] == 3
        assert result["value"]["format"] == "rle"
        assert result["value"]["brushlabels"] == list(spec["labels"])
        assert result["value"]["rle"]


def test_build_missing_file_raises_with_ids(tmp_path: Path) -> None:
    item = _seg_item("masks/missing.png")
    with pytest.raises(ValueError, match="demo_batch__000001") as exc_info:
        build_seg_brush_results(item, mask_root=tmp_path)
    assert "demo_batch__seg" in str(exc_info.value)
    assert "mask_ref" in str(exc_info.value)


def test_build_size_mismatch_with_metadata_raises(tmp_path: Path) -> None:
    mask_path = tmp_path / "masks" / "a.png"
    _save_l_mask(mask_path, [[1]])
    item = _seg_item("masks/a.png")
    with pytest.raises(ValueError, match="does not match image_metadata"):
        build_seg_brush_results(
            item,
            mask_root=tmp_path,
            image_metadata=ImageMetadata(width=10, height=10),
        )


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


def test_item_without_mask_root_keeps_empty_result() -> None:
    task = item_to_ls_task(_seg_item())
    assert task["predictions"][0]["result"] == []


def test_item_with_mask_root_emits_brush_results(tmp_path: Path) -> None:
    _save_l_mask(tmp_path / "masks" / "a.png", [[1, 0], [0, 1]])
    task = item_to_ls_task(
        _seg_item(), mask_root=tmp_path, seg_prefill_mode="brush"
    )
    # diagonal 8-connected → one component
    assert len(task["predictions"][0]["result"]) == 1
    assert task["data"]["mask_ref"] == "masks/a.png"
    assert task["predictions"][0]["result"][0]["type"] == "brushlabels"


def test_document_to_ls_tasks_passes_mask_root(tmp_path: Path) -> None:
    _save_l_mask(tmp_path / "masks" / "a.png", [[1, 0, 0], [0, 0, 1]])
    item = _seg_item("masks/a.png")
    document = PrelabelDocument(
        schema_version=SCHEMA_VERSION,
        batch_id=item.batch_id,
        package_id=item.package_id,
        task_type=TaskType.SEG,
        items=(item,),
    )
    tasks = document_to_ls_tasks(
        document, mask_root=tmp_path, seg_prefill_mode="brush"
    )
    assert len(tasks[0]["predictions"][0]["result"]) == 2


def test_empty_foreground_file_yields_empty_result(tmp_path: Path) -> None:
    _save_l_mask(tmp_path / "masks" / "a.png", [[0, 0], [0, 0]])
    results = build_seg_brush_results(_seg_item(), mask_root=tmp_path)
    assert results == []


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
    from mma.converters.seg_brush import brush_results_to_binary_mask

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
