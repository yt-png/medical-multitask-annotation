"""Tests for merge readiness validation (T5.1)."""

from __future__ import annotations

from pathlib import Path

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
from mma.common.paths import results_current_dir
from mma.exporters import overwrite_current
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.merge import validate_ready


def _seg(
    image_id: str,
    *,
    needs_rework: bool = False,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=f"masks/{image_id}.png"),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def _det(
    image_id: str,
    *,
    needs_rework: bool = False,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def _cap(
    image_id: str,
    *,
    needs_rework: bool = False,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=f"cap-{image_id}"),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def _write_processed(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-a", "img-b"),
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
    image_ids: tuple[str, ...] = ("img-a", "img-b"),
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
    _write_processed(data_root, batch_id, image_ids=image_ids)


def test_validate_ready_success(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1")
    assert validate_ready("batch1", data_root=tmp_path) is None
    assert not (tmp_path / "final").exists()


def test_missing_current_file_raises(tmp_path: Path) -> None:
    overwrite_current(
        [_seg("img-a")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    with pytest.raises(FileNotFoundError):
        validate_ready("batch1", data_root=tmp_path)


def test_empty_current_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
    empty_path = (
        results_current_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    )
    write_json(empty_path, [])
    with pytest.raises(ValueError, match="non-empty"):
        validate_ready("batch1", data_root=tmp_path)


def test_needs_rework_residual_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    overwrite_current(
        [_cap("img-b", needs_rework=True)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="needs_rework residual") as exc:
        validate_ready("batch1", data_root=tmp_path)
    assert "CAP:img-b" in str(exc.value)


def test_human_confirmed_missing_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
    overwrite_current(
        [_seg("img-a", human_confirmed=False)],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="human_confirmed missing") as exc:
        validate_ready("batch1", data_root=tmp_path)
    assert "SEG:img-a" in str(exc.value)


def test_empty_task_payload_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-a",
                task_type=TaskType.DET,
                annotation=DetAnnotation(bboxes=()),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="empty task payload") as exc:
        validate_ready("batch1", data_root=tmp_path)
    assert "DET:img-a" in str(exc.value)


def test_empty_seg_has_foreground_false_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-a",
                task_type=TaskType.SEG,
                annotation=SegAnnotation(
                    mask_ref="manual_masks/img-a_manual.png",
                    has_foreground=False,
                ),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="empty task payload") as exc:
        validate_ready("batch1", data_root=tmp_path)
    assert "SEG:img-a" in str(exc.value)


def test_multiple_flag_violations_aggregated(tmp_path: Path) -> None:
    overwrite_current(
        [
            _seg("img-a", needs_rework=True),
            _seg("img-b", human_confirmed=False),
        ],
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
        [_cap("img-a"), _cap("img-b")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError) as exc:
        validate_ready("batch1", data_root=tmp_path)
    message = str(exc.value)
    assert "needs_rework residual" in message
    assert "human_confirmed missing" in message
    assert "SEG:img-a" in message
    assert "SEG:img-b" in message


def test_image_id_set_mismatch_raises(tmp_path: Path) -> None:
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
        [_cap("img-a")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="image_id sets differ") as exc:
        validate_ready("batch1", data_root=tmp_path)
    message = str(exc.value)
    assert "only_in_SEG" in message
    assert "img-b" in message
    assert "missing_in_DET" in message or "missing_in_CAP" in message


def test_subset_vs_processed_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    with pytest.raises(ValueError, match="does not match processed") as exc:
        validate_ready("batch1", data_root=tmp_path)
    message = str(exc.value)
    assert "batch_id='batch1'" in message
    assert "only_in_processed" in message
    assert "img-b" in message


def test_extra_current_vs_processed_raises(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    with pytest.raises(ValueError, match="does not match processed") as exc:
        validate_ready("batch1", data_root=tmp_path)
    message = str(exc.value)
    assert "batch_id='batch1'" in message
    assert "only_in_current" in message
    assert "img-b" in message


def test_missing_processed_manifest_raises(tmp_path: Path) -> None:
    overwrite_current(
        [_seg("img-a")],
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
        [_cap("img-a")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(FileNotFoundError, match="processed manifest") as exc:
        validate_ready("batch1", data_root=tmp_path)
    assert "processed" in str(exc.value)


def test_invalid_batch_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        validate_ready("bad/id", data_root=tmp_path)


def test_does_not_create_final_dir(tmp_path: Path) -> None:
    _write_ready_triple(tmp_path, "batch1")
    validate_ready("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1").exists()
