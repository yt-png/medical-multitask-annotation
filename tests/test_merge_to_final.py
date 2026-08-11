"""Tests for final multitask dataset write / merge_to_final (T5.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mma.common.io import write_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.exporters import overwrite_current
from mma.merge import merge_to_final, write_final_manifest
from mma.merge.write_final import FINAL_MANIFEST_NAME


def _seg(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=f"masks/{image_id}.png"),
        human_confirmed=True,
        needs_rework=False,
    )


def _det(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
        human_confirmed=True,
        needs_rework=False,
    )


def _cap(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=f"cap-{image_id}"),
        human_confirmed=True,
        needs_rework=False,
    )


def _write_ready_currents(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
) -> None:
    overwrite_current(
        [_seg(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=data_root,
    )
    overwrite_current(
        [_det(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=data_root,
    )
    overwrite_current(
        [_cap(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=data_root,
    )


def _write_processed(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
) -> None:
    items = [
        {
            "image_id": image_id,
            "image_path": f"/img/{image_id}.jpg",
            "diagnosis_text": f"diag-{image_id}",
            "source_image_name": f"{image_id}.jpg",
        }
        for image_id in image_ids
    ]
    write_json(
        data_root / "processed" / batch_id / "manifest.json",
        {"batch_id": batch_id, "items": items},
    )


def test_write_final_manifest_shape(tmp_path: Path) -> None:
    records = (
        MergedMultitaskRecord(
            image_id="img-a",
            seg=SegAnnotation(mask_ref="m.png"),
            det=DetAnnotation(bboxes=(BBox(x=0.0, y=0.0, width=1.0, height=1.0),)),
            cap=CapAnnotation(caption="c"),
            image_path="/a.jpg",
            diagnosis_text="d",
        ),
    )
    path = write_final_manifest(records, batch_id="batch1", data_root=tmp_path)
    assert path == tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch1"
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["image_id"] == "img-a"
    assert item["image_path"] == "/a.jpg"
    assert item["diagnosis_text"] == "d"
    assert item["seg"] == {"mask_ref": "m.png"}
    assert item["det"]["bboxes"][0]["width"] == 1.0
    assert item["cap"] == {"caption": "c"}


def test_merge_to_final_success_order_and_enrich(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1")
    _write_processed(tmp_path, "batch1")
    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch1"
    assert [item["image_id"] for item in payload["items"]] == ["img-b", "img-a"]
    first = payload["items"][0]
    assert first["image_path"] == "/img/img-b.jpg"
    assert first["diagnosis_text"] == "diag-img-b"
    assert first["seg"]["mask_ref"] == "masks/img-b.png"
    assert first["cap"]["caption"] == "cap-img-b"


def test_merge_to_final_overwrites(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    path = merge_to_final("batch1", data_root=tmp_path)
    path.write_text('{"batch_id":"batch1","items":[]}\n', encoding="utf-8")
    merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    assert payload["items"][0]["image_id"] == "img-a"


def test_merge_to_final_not_ready_preserves_old(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    path = merge_to_final("batch1", data_root=tmp_path)
    old = path.read_text(encoding="utf-8")
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-a",
                task_type=TaskType.CAP,
                annotation=CapAnnotation(caption="x"),
                human_confirmed=True,
                needs_rework=True,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="needs_rework"):
        merge_to_final("batch1", data_root=tmp_path)
    assert path.read_text(encoding="utf-8") == old


def test_merge_to_final_missing_task_does_not_write(tmp_path: Path) -> None:
    overwrite_current(
        [_seg("img-a"), _seg("img-b")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det("img-a"), _det("img-b")],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap("img-a")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    with patch("mma.merge.merge_multitask.validate_ready", return_value=None):
        with pytest.raises(ValueError, match="missing CAP"):
            merge_to_final("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_merge_to_final_missing_processed(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    with pytest.raises(FileNotFoundError, match="processed manifest"):
        merge_to_final("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_merge_to_final_missing_processed_image_id(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    with pytest.raises(ValueError, match="not found in processed"):
        merge_to_final("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_invalid_batch_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        merge_to_final("bad/id", data_root=tmp_path)
