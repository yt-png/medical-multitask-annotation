"""LEGACY: PrelabelItem SEG geometry → LS conversion.

Not part of the V1 runtime test suite; run with ``pytest -m legacy``.
V1 mask ↔ LS geometry stays in ``tests/test_seg_polygon.py`` and
``tests/test_seg_brush.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.models import TaskType
from mma.converters import DEFAULT_LS_RESULT_SPECS, ImageMetadata
from mma.converters.seg_brush import build_seg_brush_results
from mma.converters.seg_polygon import build_seg_polygon_results
from mma.formats.legacy_prelabel import (
    PrelabelDocument,
    PrelabelItem,
    SCHEMA_VERSION,
    SegPrelabelPayload,
)
from mma.legacy.converters import document_to_ls_tasks, item_to_ls_task

pytestmark = pytest.mark.legacy


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


def test_build_polygon_size_mismatch_raises(tmp_path: Path) -> None:
    _save_l_mask(tmp_path / "masks" / "a.png", [[1, 1], [1, 1]])
    with pytest.raises(ValueError, match="does not match image_metadata"):
        build_seg_polygon_results(
            _seg_item(),
            mask_root=tmp_path,
            image_metadata=ImageMetadata(width=10, height=10),
        )


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


def test_build_brush_size_mismatch_with_metadata_raises(tmp_path: Path) -> None:
    mask_path = tmp_path / "masks" / "a.png"
    _save_l_mask(mask_path, [[1]])
    item = _seg_item("masks/a.png")
    with pytest.raises(ValueError, match="does not match image_metadata"):
        build_seg_brush_results(
            item,
            mask_root=tmp_path,
            image_metadata=ImageMetadata(width=10, height=10),
        )


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
