"""Tests for multitask merge by image_id (T5.2 / T5.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mma.common.io import write_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import results_task_dir
from mma.converters.seg_brush import save_binary_mask_png
from mma.exporters import overwrite_current
from mma.merge import assert_no_missing_tasks, merge_multitask
from mma.merge.merge_multitask import _require_annotation


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


def _write_processed(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...],
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


def _write_ready_triple(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
) -> None:
    """Write three currents + matching processed; SEG order is ``image_ids``."""

    overwrite_current(
        [_seg(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=data_root,
    )
    for image_id in image_ids:
        mask_path = (
            results_task_dir(batch_id, TaskType.SEG, data_root=data_root)
            / "masks"
            / f"{image_id}.png"
        )
        save_binary_mask_png(mask_path, [[1]])
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
    _write_processed(data_root, batch_id, image_ids)


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


def test_merge_missing_cap_after_validate_bypass(tmp_path: Path) -> None:
    """T5.3: secondary check blocks missing CAP when validate_ready is bypassed."""

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


def test_merge_missing_det_after_validate_bypass(tmp_path: Path) -> None:
    """T5.3: secondary check blocks missing DET when validate_ready is bypassed."""

    overwrite_current(
        [_seg("img-a"), _seg("img-b")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det("img-a")],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap("img-a"), _cap("img-b")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with patch("mma.merge.merge_multitask.validate_ready", return_value=None):
        with pytest.raises(ValueError, match="missing DET") as exc:
            merge_multitask("batch1", data_root=tmp_path)
    assert "img-b" in str(exc.value)


def test_assert_no_missing_tasks_ok() -> None:
    det_by_id = {"img-a": _det("img-a")}
    cap_by_id = {"img-a": _cap("img-a")}
    assert_no_missing_tasks("img-a", det_by_id, cap_by_id)


def test_assert_no_missing_tasks_missing_det() -> None:
    with pytest.raises(ValueError, match="missing DET") as exc:
        assert_no_missing_tasks("img-a", {}, {"img-a": _cap("img-a")})
    assert "img-a" in str(exc.value)


def test_assert_no_missing_tasks_missing_cap() -> None:
    with pytest.raises(ValueError, match="missing CAP") as exc:
        assert_no_missing_tasks("img-a", {"img-a": _det("img-a")}, {})
    assert "img-a" in str(exc.value)


def test_require_annotation_type_mismatch() -> None:
    """T5.3: wrong annotation type is blocked (no silent field reuse)."""

    item = _cap("img-a")
    with pytest.raises(ValueError, match="type mismatch") as exc:
        _require_annotation(
            item,
            DetAnnotation,
            image_id="img-a",
            task_label="DET",
        )
    assert "img-a" in str(exc.value)
    assert "DetAnnotation" in str(exc.value)


def test_invalid_batch_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        merge_multitask("bad/id", data_root=tmp_path)


def test_does_not_write_final(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1")
    merge_multitask("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1").exists()
