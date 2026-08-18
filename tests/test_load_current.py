"""Tests for loading current annotations (T4.5)."""

from __future__ import annotations

import json
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
    should_rework_result,
)
from mma.common.paths import results_current_dir
from mma.exporters import load_current, load_current_annotations_file, overwrite_current

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_RESULTS = _REPO_ROOT / "data" / "results" / "demo_batch"


def _cap(image_id: str, *, caption: str, needs_rework: bool = False) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=caption),
        human_confirmed=True,
        needs_rework=needs_rework,
        package_id="pkg__cap",
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


def test_roundtrip_seg_det_cap_via_overwrite(tmp_path: Path) -> None:
    overwrite_current(
        [_seg("s1", mask_ref="masks/s1.png")],
        batch_id="b1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [
            _det("d1", bboxes=(BBox(1.0, 2.0, 3.0, 4.0),)),
            _det("d2", bboxes=()),
        ],
        batch_id="b1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [
            _cap("c1", caption="first"),
            _cap("c2", caption="second", needs_rework=True),
        ],
        batch_id="b1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )

    seg = load_current("b1", TaskType.SEG, data_root=tmp_path)
    det = load_current("b1", TaskType.DET, data_root=tmp_path)
    cap = load_current("b1", TaskType.CAP, data_root=tmp_path)

    assert len(seg) == 1
    assert isinstance(seg[0].annotation, SegAnnotation)
    assert seg[0].annotation.mask_ref == "masks/s1.png"
    assert seg[0].annotation.has_foreground is True

    assert [x.image_id for x in det] == ["d1", "d2"]
    assert det[0].annotation.bboxes == (BBox(1.0, 2.0, 3.0, 4.0),)
    assert det[1].annotation.bboxes == ()

    assert [x.image_id for x in cap] == ["c1", "c2"]
    assert cap[0].annotation.caption == "first"
    assert cap[1].needs_rework is True
    assert cap[0].package_id == "pkg__cap"


def test_load_current_annotations_file_helper(tmp_path: Path) -> None:
    path = overwrite_current(
        [_cap("x1", caption="via path")],
        batch_id="b1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    loaded = load_current_annotations_file(path, task_type=TaskType.CAP)
    assert len(loaded) == 1
    assert loaded[0].annotation.caption == "via path"


def test_cap_empty_caption_human_clear_roundtrip(tmp_path: Path) -> None:
    """Empty caption is a valid human-clear state, not rejected on reload."""

    path = overwrite_current(
        [_cap("cleared", caption="")],
        batch_id="b1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    loaded = load_current_annotations_file(path, task_type=TaskType.CAP)
    assert len(loaded) == 1
    assert loaded[0].annotation.caption == ""


def test_seg_has_foreground_roundtrip(tmp_path: Path) -> None:
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="empty-fg",
                task_type=TaskType.SEG,
                annotation=SegAnnotation(
                    mask_ref="manual_masks/empty-fg_manual.png",
                    has_foreground=False,
                ),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id="b1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    loaded = load_current("b1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.has_foreground is False


def test_seg_json_missing_has_foreground_defaults_false(
    tmp_path: Path,
) -> None:
    path = (
        results_current_dir("b1", TaskType.SEG, data_root=tmp_path)
        / "annotations.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        path,
        [
            {
                "image_id": "legacy",
                "task_type": "SEG",
                "annotation": {"mask_ref": "masks/legacy.png"},
                "human_confirmed": True,
                "needs_rework": False,
                "package_id": None,
                "export_round": None,
            }
        ],
    )
    loaded = load_current("b1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.has_foreground is False
    assert should_rework_result(loaded[0]) is True


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = (
        results_current_dir("b1", TaskType.CAP, data_root=tmp_path)
        / "annotations.json"
    )
    with pytest.raises(FileNotFoundError):
        load_current("b1", TaskType.CAP, data_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        load_current_annotations_file(missing, task_type=TaskType.CAP)


def test_invalid_root_not_array_raises(tmp_path: Path) -> None:
    path = (
        results_current_dir("b1", TaskType.CAP, data_root=tmp_path)
        / "annotations.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {"items": []})
    with pytest.raises(ValueError, match="JSON array"):
        load_current("b1", TaskType.CAP, data_root=tmp_path)


def test_duplicate_image_id_raises(tmp_path: Path) -> None:
    path = (
        results_current_dir("b1", TaskType.CAP, data_root=tmp_path)
        / "annotations.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "image_id": "dup",
        "task_type": "CAP",
        "annotation": {"caption": "a"},
        "human_confirmed": True,
        "needs_rework": False,
        "package_id": None,
        "export_round": None,
    }
    write_json(path, [row, dict(row)])
    with pytest.raises(ValueError, match="duplicate image_id"):
        load_current("b1", TaskType.CAP, data_root=tmp_path)


def test_task_type_mismatch_raises(tmp_path: Path) -> None:
    path = overwrite_current(
        [_cap("x1", caption="cap only")],
        batch_id="b1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="does not match"):
        load_current_annotations_file(path, task_type=TaskType.SEG)


@pytest.mark.skipif(
    not (_DEMO_RESULTS / "cap" / "current" / "annotations.json").is_file(),
    reason="demo_batch current annotations not present under data/results",
)
def test_demo_batch_smoke_optional() -> None:
    for task_type, key in (
        (TaskType.SEG, "seg"),
        (TaskType.DET, "det"),
        (TaskType.CAP, "cap"),
    ):
        path = _DEMO_RESULTS / key / "current" / "annotations.json"
        if not path.is_file():
            pytest.skip(f"missing {path}")
        items = load_current("demo_batch", task_type, data_root=_REPO_ROOT / "data")
        assert items
        assert all(item.task_type is task_type for item in items)
        # Ensure file remains valid JSON array.
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, list) and payload
