"""Tests for current/ overwrite (T4.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.io import read_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import results_current_dir
from mma.exporters import overwrite_current


def _cap(
    image_id: str,
    *,
    caption: str,
    needs_rework: bool,
    export_round: int | None = None,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=caption),
        human_confirmed=True,
        needs_rework=needs_rework,
        package_id="demo__cap",
        export_round=export_round,
    )


def _seg(image_id: str, *, mask_ref: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=mask_ref),
        human_confirmed=True,
        needs_rework=False,
    )


def _det(image_id: str, *, bboxes: tuple[BBox, ...]) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=bboxes),
        human_confirmed=True,
        needs_rework=False,
    )


def test_first_write_creates_annotations_json(tmp_path: Path) -> None:
    path = overwrite_current(
        [_cap("img-a", caption="v1", needs_rework=True, export_round=1)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    expected = (
        results_current_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / "annotations.json"
    )
    assert path == expected.resolve()
    assert path.is_file()
    payload = read_json(path)
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["image_id"] == "img-a"
    assert payload[0]["annotation"]["caption"] == "v1"
    assert payload[0]["needs_rework"] is True
    assert payload[0]["human_confirmed"] is True
    assert payload[0]["task_type"] == "CAP"


def test_same_image_id_overwrites_annotation_and_checkboxes(tmp_path: Path) -> None:
    overwrite_current(
        [_cap("img-a", caption="old", needs_rework=True, export_round=1)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    path = overwrite_current(
        [_cap("img-a", caption="new", needs_rework=False, export_round=2)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    payload = read_json(path)
    assert len(payload) == 1
    assert payload[0]["annotation"]["caption"] == "new"
    assert payload[0]["needs_rework"] is False
    assert payload[0]["export_round"] == 2


def test_subset_merge_preserves_other_ids_and_order(tmp_path: Path) -> None:
    overwrite_current(
        [
            _cap("img-a", caption="a1", needs_rework=False),
            _cap("img-b", caption="b1", needs_rework=True),
        ],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    path = overwrite_current(
        [_cap("img-a", caption="a2", needs_rework=True)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    payload = read_json(path)
    assert [row["image_id"] for row in payload] == ["img-a", "img-b"]
    assert payload[0]["annotation"]["caption"] == "a2"
    assert payload[0]["needs_rework"] is True
    assert payload[1]["annotation"]["caption"] == "b1"


def test_new_image_id_appended(tmp_path: Path) -> None:
    overwrite_current(
        [_cap("img-a", caption="a", needs_rework=False)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    path = overwrite_current(
        [_cap("img-c", caption="c", needs_rework=False)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    payload = read_json(path)
    assert [row["image_id"] for row in payload] == ["img-a", "img-c"]


def test_seg_det_shapes(tmp_path: Path) -> None:
    seg_path = overwrite_current(
        [_seg("s1", mask_ref="masks/s1.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    det_path = overwrite_current(
        [
            _det("d1", bboxes=(BBox(1.0, 2.0, 3.0, 4.0),)),
            _det("d2", bboxes=()),
        ],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    seg = read_json(seg_path)
    det = read_json(det_path)
    assert seg[0]["annotation"] == {
        "mask_ref": "masks/s1.png",
        "has_foreground": True,
    }
    assert det[0]["annotation"]["bboxes"] == [
        {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}
    ]
    assert det[1]["annotation"]["bboxes"] == []


def test_empty_results_noop_keeps_existing(tmp_path: Path) -> None:
    first = overwrite_current(
        [_cap("img-a", caption="keep", needs_rework=False)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    before = first.read_text(encoding="utf-8")
    path = overwrite_current(
        (),
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert path == first
    assert path.read_text(encoding="utf-8") == before


def test_empty_results_without_existing_file_returns_path(tmp_path: Path) -> None:
    path = overwrite_current(
        (),
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    expected = (
        results_current_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / "annotations.json"
    )
    assert path == expected.resolve()
    assert not path.exists()


def test_duplicate_image_id_in_batch_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate image_id"):
        overwrite_current(
            [
                _cap("dup", caption="a", needs_rework=False),
                _cap("dup", caption="b", needs_rework=True),
            ],
            batch_id="batch1",
            task_type=TaskType.CAP,
            data_root=tmp_path,
        )


def test_task_type_mismatch_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        overwrite_current(
            [_cap("img-a", caption="x", needs_rework=False)],
            batch_id="batch1",
            task_type=TaskType.SEG,
            data_root=tmp_path,
        )
