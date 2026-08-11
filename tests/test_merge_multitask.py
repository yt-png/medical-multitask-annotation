"""Tests for multitask merge by image_id (T5.2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.exporters import overwrite_current
from mma.merge import merge_multitask


def _seg(image_id: str, *, mask_ref: str | None = None) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=mask_ref or f"masks/{image_id}.png"),
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


def _cap(image_id: str, *, caption: str | None = None) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=caption or f"cap-{image_id}"),
        human_confirmed=True,
        needs_rework=False,
    )


def _write_ready_triple(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
) -> None:
    """Write three currents; SEG order is given by ``image_ids``."""

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


def test_merge_success_order_and_payloads(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-b", "img-a"))
    records = merge_multitask("batch1", data_root=tmp_path)
    assert len(records) == 2
    assert records[0].image_id == "img-b"
    assert records[1].image_id == "img-a"
    assert isinstance(records[0].seg, SegAnnotation)
    assert records[0].seg.mask_ref == "masks/img-b.png"
    assert isinstance(records[0].det, DetAnnotation)
    assert records[0].det.bboxes[0].x == 1.0
    assert isinstance(records[0].cap, CapAnnotation)
    assert records[0].cap.caption == "cap-img-b"
    assert records[0].image_path is None
    assert records[0].diagnosis_text is None
    assert not (tmp_path / "final").exists()


def test_merge_rejects_not_ready(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
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
        merge_multitask("batch1", data_root=tmp_path)


def test_merge_missing_task_after_validate_bypass(tmp_path: Path) -> None:
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
    with patch("mma.merge.merge_multitask.validate_ready", return_value=None):
        with pytest.raises(ValueError, match="missing CAP") as exc:
            merge_multitask("batch1", data_root=tmp_path)
    assert "img-b" in str(exc.value)


def test_invalid_batch_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        merge_multitask("bad/id", data_root=tmp_path)


def test_does_not_write_final(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1")
    merge_multitask("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1").exists()
