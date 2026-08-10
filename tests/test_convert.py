"""Tests for intermediate → Label Studio import conversion (T2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.models import TaskType
from mma.converters import (
    DATA_KEY_DIAGNOSIS_TEXT,
    DATA_KEY_IMAGE,
    DATA_KEY_IMAGE_ID,
    DATA_KEY_MASK_REF,
    DEFAULT_LS_RESULT_SPECS,
    MODEL_VERSION,
    ImageMetadata,
    document_to_ls_tasks,
    item_to_ls_task,
)
from mma.formats import (
    CapPrelabelPayload,
    DetPrelabelPayload,
    PrelabelBBox,
    PrelabelDocument,
    PrelabelItem,
    SCHEMA_VERSION,
    SegPrelabelPayload,
    load_prelabel_document,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FORMATS_DIR = _REPO_ROOT / "src" / "mma" / "formats"


def _meta_map_for_document(
    document: PrelabelDocument,
    *,
    width: int = 640,
    height: int = 480,
) -> dict[str, ImageMetadata]:
    meta = ImageMetadata(width=width, height=height)
    return {item.image_id: meta for item in document.items}


def test_seg_document_conversion() -> None:
    document = load_prelabel_document(_FORMATS_DIR / "seg.json")
    tasks = document_to_ls_tasks(document)
    assert len(tasks) == len(document.items)

    first_item = document.items[0]
    first_task = tasks[0]
    assert first_task["id"] == first_item.image_id
    assert first_task["data"][DATA_KEY_IMAGE_ID] == first_item.image_id
    assert first_task["data"][DATA_KEY_IMAGE] == first_item.image_path
    assert first_task["data"][DATA_KEY_MASK_REF] == first_item.payload.mask_ref  # type: ignore[union-attr]
    assert first_task["data"][DATA_KEY_DIAGNOSIS_TEXT] == first_item.diagnosis_text
    assert first_task["predictions"][0]["model_version"] == MODEL_VERSION
    assert first_task["predictions"][0]["result"] == []


def test_det_document_percent_conversion() -> None:
    document = load_prelabel_document(_FORMATS_DIR / "det.json")
    meta_by_id = _meta_map_for_document(document, width=640, height=480)
    tasks = document_to_ls_tasks(document, image_metadata_by_id=meta_by_id)

    multi = next(t for t in tasks if t["id"] == "demo_batch__000001")
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.DET]
    results = multi["predictions"][0]["result"]
    assert len(results) == 2

    first = results[0]
    assert first["from_name"] == spec["from_name"]
    assert first["to_name"] == spec["to_name"]
    assert first["type"] == spec["type"]
    assert first["original_width"] == 640
    assert first["original_height"] == 480
    # pixel (120, 80.5, 64, 48) on 640x480
    assert first["value"]["x"] == pytest.approx(120.0 / 640.0 * 100.0)
    assert first["value"]["y"] == pytest.approx(80.5 / 480.0 * 100.0)
    assert first["value"]["width"] == pytest.approx(64.0 / 640.0 * 100.0)
    assert first["value"]["height"] == pytest.approx(48.0 / 480.0 * 100.0)
    assert first["value"]["rectanglelabels"] == list(spec["labels"])

    empty = next(t for t in tasks if t["id"] == "demo_batch__000002")
    assert empty["predictions"][0]["result"] == []


def test_cap_document_keeps_diagnosis_and_caption_separate() -> None:
    document = load_prelabel_document(_FORMATS_DIR / "cap.json")
    tasks = document_to_ls_tasks(document)
    item = document.items[0]
    task = tasks[0]
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]

    assert task["data"][DATA_KEY_DIAGNOSIS_TEXT] == item.diagnosis_text
    assert isinstance(item.payload, CapPrelabelPayload)
    result = task["predictions"][0]["result"][0]
    assert result["from_name"] == spec["from_name"]
    assert result["to_name"] == spec["to_name"]
    assert result["type"] == spec["type"]
    assert result["value"]["text"] == [item.payload.caption]
    assert item.payload.caption != item.diagnosis_text


def test_det_item_requires_metadata() -> None:
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="demo_batch",
        package_id="demo_batch__det",
        task_type=TaskType.DET,
        image_id="demo_batch__000099",
        diagnosis_text="diag",
        payload=DetPrelabelPayload(
            bboxes=(PrelabelBBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
    )
    with pytest.raises(ValueError, match="image_metadata"):
        item_to_ls_task(item)


def test_det_document_missing_metadata_for_one_id() -> None:
    document = load_prelabel_document(_FORMATS_DIR / "det.json")
    only_first = {
        document.items[0].image_id: ImageMetadata(width=100, height=100),
    }
    with pytest.raises(ValueError, match="missing image_metadata"):
        document_to_ls_tasks(document, image_metadata_by_id=only_first)


def test_image_metadata_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="width/height"):
        ImageMetadata(width=0, height=10)


def test_seg_and_cap_ignore_metadata() -> None:
    seg = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="b",
        package_id="b__seg",
        task_type=TaskType.SEG,
        image_id="b__000001",
        diagnosis_text="diag",
        payload=SegPrelabelPayload(mask_ref="masks/a.png"),
        image_path=None,
    )
    task = item_to_ls_task(seg, image_metadata=ImageMetadata(width=10, height=10))
    assert task["data"][DATA_KEY_IMAGE] is None
    assert task["data"][DATA_KEY_MASK_REF] == "masks/a.png"
    assert task["predictions"][0]["result"] == []


def test_seg_with_mask_root_emits_brush_results(tmp_path: Path) -> None:
    from PIL import Image

    mask_dir = tmp_path / "masks"
    mask_dir.mkdir()
    img = Image.new("L", (4, 4), 0)
    img.putpixel((0, 0), 255)
    img.putpixel((3, 3), 255)
    img.save(mask_dir / "a.png")

    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="b",
        package_id="b__seg",
        task_type=TaskType.SEG,
        image_id="b__000001",
        diagnosis_text="diag",
        payload=SegPrelabelPayload(mask_ref="masks/a.png"),
    )
    task = item_to_ls_task(item, mask_root=tmp_path)
    results = task["predictions"][0]["result"]
    assert len(results) == 2
    assert results[0]["value"]["format"] == "rle"
    assert results[0]["from_name"] == "seg_mask"
    assert task["data"][DATA_KEY_MASK_REF] == "masks/a.png"


def test_det_empty_bboxes_keeps_predictions_structure() -> None:
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="b",
        package_id="b__det",
        task_type=TaskType.DET,
        image_id="b__000001",
        diagnosis_text="diag",
        payload=DetPrelabelPayload(bboxes=()),
    )
    task = item_to_ls_task(item, image_metadata=ImageMetadata(width=100, height=80))
    assert task["predictions"][0]["result"] == []
    assert task["predictions"][0]["model_version"] == MODEL_VERSION
