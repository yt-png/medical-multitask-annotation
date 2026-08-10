"""Tests for unified prelabel intermediate formats (T2.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mma.common.models import TaskType
from mma.formats import (
    SCHEMA_VERSION,
    CapPrelabelPayload,
    DetPrelabelPayload,
    PrelabelBBox,
    PrelabelDocument,
    PrelabelItem,
    SegPrelabelPayload,
    assert_payload_matches_task,
    load_prelabel_document,
    prelabel_document_from_dict,
    prelabel_document_to_dict,
    prelabel_item_from_dict,
)
from mma.formats.intermediate import validate_prelabel_document

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FORMATS_DIR = _REPO_ROOT / "src" / "mma" / "formats"
_EXAMPLES_PRELABELS = _REPO_ROOT / "examples" / "prelabels" / "demo_batch"


def _minimal_item_dict(
    *,
    task_type: str = "SEG",
    image_id: str = "demo_batch__000001",
    payload: dict | None = None,
    **overrides: object,
) -> dict:
    if payload is None:
        payload = {"mask_ref": "masks/a.png"}
    data: dict = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": "demo_batch",
        "package_id": "demo_batch__seg",
        "task_type": task_type,
        "image_id": image_id,
        "diagnosis_text": "original diagnosis",
        "payload": payload,
    }
    data.update(overrides)
    return data


def _minimal_document_dict(
    *,
    task_type: str = "SEG",
    package_id: str = "demo_batch__seg",
    items: list | None = None,
) -> dict:
    if items is None:
        items = [_minimal_item_dict(task_type=task_type, package_id=package_id)]
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": "demo_batch",
        "package_id": package_id,
        "task_type": task_type,
        "items": items,
    }


@pytest.mark.parametrize(
    ("filename", "task_type"),
    [
        ("seg.json", TaskType.SEG),
        ("det.json", TaskType.DET),
        ("cap.json", TaskType.CAP),
    ],
)
def test_load_packaged_format_samples(filename: str, task_type: TaskType) -> None:
    path = _FORMATS_DIR / filename
    document = load_prelabel_document(path)
    assert document.task_type is task_type
    assert document.schema_version == SCHEMA_VERSION
    assert len(document.items) >= 1
    assert {item.image_id for item in document.items}


@pytest.mark.parametrize("task", ("seg", "det", "cap"))
def test_load_examples_prelabels_json(task: str) -> None:
    path = _EXAMPLES_PRELABELS / task / "prelabels.json"
    document = load_prelabel_document(path)
    assert document.task_type.value == task.upper()
    assert document.items


def test_roundtrip_document_dict() -> None:
    original = load_prelabel_document(_FORMATS_DIR / "det.json")
    restored = prelabel_document_from_dict(prelabel_document_to_dict(original))
    assert restored == original


def test_construct_seg_item_without_image_path() -> None:
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id="demo_batch",
        package_id="demo_batch__seg",
        task_type=TaskType.SEG,
        image_id="demo_batch__000001",
        diagnosis_text="diag",
        payload=SegPrelabelPayload(mask_ref="masks/a.png"),
    )
    assert item.image_path is None


def test_det_allows_empty_bboxes_and_pixel_origin() -> None:
    empty = DetPrelabelPayload(bboxes=())
    assert empty.bboxes == ()
    box = PrelabelBBox(x=0.0, y=0.0, width=1.0, height=2.0)
    assert box.x == 0.0


def test_cap_caption_distinct_from_diagnosis() -> None:
    item = prelabel_item_from_dict(
        _minimal_item_dict(
            task_type="CAP",
            package_id="demo_batch__cap",
            payload={"caption": "model caption"},
            diagnosis_text="original excel text",
        )
    )
    assert isinstance(item.payload, CapPrelabelPayload)
    assert item.payload.caption == "model caption"
    assert item.diagnosis_text == "original excel text"


def test_assert_payload_matches_task_rejects_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        assert_payload_matches_task(
            TaskType.SEG,
            CapPrelabelPayload(caption="x"),
        )


def test_bbox_rejects_negative_and_non_positive_size() -> None:
    with pytest.raises(ValueError, match="x/y"):
        PrelabelBBox(x=-1.0, y=0.0, width=1.0, height=1.0)
    with pytest.raises(ValueError, match="width/height"):
        PrelabelBBox(x=0.0, y=0.0, width=0.0, height=1.0)


def test_seg_rejects_empty_mask_ref() -> None:
    with pytest.raises(ValueError, match="mask_ref"):
        SegPrelabelPayload(mask_ref="  ")


def test_cap_rejects_empty_caption() -> None:
    with pytest.raises(ValueError, match="caption"):
        CapPrelabelPayload(caption="")


def test_parse_rejects_missing_fields() -> None:
    raw = _minimal_item_dict()
    del raw["image_id"]
    with pytest.raises(ValueError, match="image_id"):
        prelabel_item_from_dict(raw)


def test_parse_rejects_task_payload_mismatch() -> None:
    raw = _minimal_item_dict(
        task_type="DET",
        package_id="demo_batch__det",
        payload={"mask_ref": "masks/a.png"},
    )
    with pytest.raises(ValueError, match="bboxes"):
        prelabel_item_from_dict(raw)


def test_document_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="empty"):
        prelabel_document_from_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "batch_id": "demo_batch",
                "package_id": "demo_batch__seg",
                "task_type": "SEG",
                "items": [],
            }
        )


def test_document_rejects_duplicate_image_id() -> None:
    item = _minimal_item_dict(image_id="same-id")
    raw = _minimal_document_dict(items=[item, dict(item)])
    with pytest.raises(ValueError, match="duplicate image_id"):
        prelabel_document_from_dict(raw)


def test_document_rejects_metadata_mismatch() -> None:
    item = _minimal_item_dict(batch_id="other_batch")
    raw = _minimal_document_dict(items=[item])
    with pytest.raises(ValueError, match="batch_id"):
        prelabel_document_from_dict(raw)


def test_image_path_empty_string_rejected() -> None:
    raw = _minimal_item_dict(image_path="")
    with pytest.raises(ValueError, match="image_path"):
        prelabel_item_from_dict(raw)


def test_validate_prelabel_document_on_constructed_object() -> None:
    document = PrelabelDocument(
        schema_version=SCHEMA_VERSION,
        batch_id="demo_batch",
        package_id="demo_batch__seg",
        task_type=TaskType.SEG,
        items=(
            PrelabelItem(
                schema_version=SCHEMA_VERSION,
                batch_id="demo_batch",
                package_id="demo_batch__seg",
                task_type=TaskType.SEG,
                image_id="demo_batch__000001",
                diagnosis_text="diag",
                payload=SegPrelabelPayload(mask_ref="masks/a.png"),
            ),
        ),
    )
    validate_prelabel_document(document)


def test_packaged_samples_are_valid_json_files() -> None:
    for name in ("seg.json", "det.json", "cap.json"):
        payload = json.loads((_FORMATS_DIR / name).read_text(encoding="utf-8"))
        assert payload["schema_version"] == SCHEMA_VERSION
