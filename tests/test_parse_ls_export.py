"""Tests for Label Studio export parsing (T4.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskType,
)
from mma.converters import ImageMetadata
from mma.exporters import parse_ls_export, parse_ls_export_data

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LS_EXPORT_ROOT = _REPO_ROOT / "data" / "ls_export" / "demo_batch"


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _cap_task(
    *,
    image_id: str,
    caption: str,
    human: str = "yes",
    rework: str | None = "no",
    package_id: str = "demo_batch__cap",
) -> dict:
    results = [
        {
            "from_name": "cap_text",
            "to_name": "image",
            "type": "textarea",
            "value": {"text": [caption]},
        },
        _choice("human_confirmed", human),
    ]
    if rework is not None:
        results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "diagnosis_text": "diag",
        },
        "annotations": [
            {
                "id": 1,
                "was_cancelled": False,
                "updated_at": "2026-08-11T00:00:00.000000Z",
                "result": results,
            }
        ],
    }


def _det_task(
    *,
    image_id: str,
    boxes_pct: list[tuple[float, float, float, float]] | None = None,
    human: str = "yes",
    rework: str | None = "no",
    package_id: str = "demo_batch__det",
) -> dict:
    results: list[dict] = []
    for x, y, w, h in boxes_pct or []:
        results.append(
            {
                "from_name": "det_bbox",
                "to_name": "image",
                "type": "rectanglelabels",
                "value": {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "rectanglelabels": ["object"],
                },
            }
        )
    results.append(_choice("human_confirmed", human))
    if rework is not None:
        results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "diagnosis_text": "diag",
        },
        "annotations": [
            {
                "id": 1,
                "was_cancelled": False,
                "updated_at": "2026-08-11T00:00:00.000000Z",
                "result": results,
            }
        ],
    }


def _seg_task(
    *,
    image_id: str,
    mask_ref: str,
    human: str = "yes",
    rework: str | None = "no",
    package_id: str = "demo_batch__seg",
    include_brush: bool = True,
) -> dict:
    results: list[dict] = []
    if include_brush:
        results.append(
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "value": {
                    "format": "rle",
                    "rle": [0, 1, 2],
                    "brushlabels": ["lesion"],
                },
            }
        )
    results.append(_choice("human_confirmed", human))
    if rework is not None:
        results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "mask_ref": mask_ref,
            "diagnosis_text": "diag",
        },
        "annotations": [
            {
                "id": 1,
                "was_cancelled": False,
                "updated_at": "2026-08-11T00:00:00.000000Z",
                "result": results,
            }
        ],
    }


def test_parse_cap_export_choices_and_caption() -> None:
    data = [
        _cap_task(image_id="img-1", caption="caption one", rework="no"),
        _cap_task(image_id="img-2", caption="caption two", rework="yes"),
    ]
    results = parse_ls_export_data(data, task_type=TaskType.CAP)
    assert len(results) == 2
    assert results[0].image_id == "img-1"
    assert results[0].task_type is TaskType.CAP
    assert isinstance(results[0].annotation, CapAnnotation)
    assert results[0].annotation.caption == "caption one"
    assert results[0].human_confirmed is True
    assert results[0].needs_rework is False
    assert results[0].package_id == "demo_batch__cap"
    assert results[0].export_round is None
    assert results[1].needs_rework is True


def test_parse_det_percent_to_pixel_with_explicit_metadata() -> None:
    # percent on 640x480 → pixel (120, 80.5, 64, 48)
    data = [
        _det_task(
            image_id="img-det-1",
            boxes_pct=[
                (120.0 / 640.0 * 100.0, 80.5 / 480.0 * 100.0, 64.0 / 640.0 * 100.0, 48.0 / 480.0 * 100.0),
                (300.0 / 640.0 * 100.0, 210.0 / 480.0 * 100.0, 40.0 / 640.0 * 100.0, 36.0 / 480.0 * 100.0),
            ],
        )
    ]
    meta = {"img-det-1": ImageMetadata(width=640, height=480)}
    results = parse_ls_export_data(
        data,
        task_type=TaskType.DET,
        image_metadata_by_id=meta,
    )
    assert len(results) == 1
    annotation = results[0].annotation
    assert isinstance(annotation, DetAnnotation)
    assert len(annotation.bboxes) == 2
    first = annotation.bboxes[0]
    assert first.x == pytest.approx(120.0)
    assert first.y == pytest.approx(80.5)
    assert first.width == pytest.approx(64.0)
    assert first.height == pytest.approx(48.0)


def test_parse_det_empty_boxes_without_metadata() -> None:
    data = [_det_task(image_id="img-empty", boxes_pct=[], rework="yes")]
    results = parse_ls_export_data(data, task_type=TaskType.DET)
    annotation = results[0].annotation
    assert isinstance(annotation, DetAnnotation)
    assert annotation.bboxes == ()
    assert results[0].needs_rework is True


def test_parse_det_with_boxes_requires_metadata() -> None:
    data = [
        _det_task(
            image_id="img-det-2",
            boxes_pct=[(10.0, 20.0, 5.0, 5.0)],
        )
    ]
    with pytest.raises(ValueError, match="image_metadata_by_id"):
        parse_ls_export_data(data, task_type=TaskType.DET)

    with pytest.raises(ValueError, match="missing image_metadata"):
        parse_ls_export_data(
            data,
            task_type=TaskType.DET,
            image_metadata_by_id={"other": ImageMetadata(width=10, height=10)},
        )


def test_parse_seg_uses_data_mask_ref_not_rle() -> None:
    data = [
        _seg_task(
            image_id="img-seg-1",
            mask_ref="masks/img-seg-1.png",
            include_brush=True,
        )
    ]
    results = parse_ls_export_data(data, task_type=TaskType.SEG)
    annotation = results[0].annotation
    assert isinstance(annotation, SegAnnotation)
    assert annotation.mask_ref == "masks/img-seg-1.png"
    assert "rle" not in annotation.mask_ref


def test_needs_rework_defaults_false_when_missing() -> None:
    data = [_cap_task(image_id="img-nr", caption="ok", rework=None)]
    results = parse_ls_export_data(data, task_type=TaskType.CAP)
    assert results[0].needs_rework is False


def test_human_confirmed_missing_or_invalid_raises() -> None:
    task = _cap_task(image_id="img-hc", caption="ok")
    task["annotations"][0]["result"] = [
        {
            "from_name": "cap_text",
            "to_name": "image",
            "type": "textarea",
            "value": {"text": ["ok"]},
        },
        _choice("needs_rework", "no"),
    ]
    with pytest.raises(ValueError, match="human_confirmed"):
        parse_ls_export_data([task], task_type=TaskType.CAP)

    task2 = _cap_task(image_id="img-hc2", caption="ok", human="maybe")
    with pytest.raises(ValueError, match="invalid choice"):
        parse_ls_export_data([task2], task_type=TaskType.CAP)


def test_duplicate_image_id_raises() -> None:
    data = [
        _cap_task(image_id="dup", caption="a"),
        _cap_task(image_id="dup", caption="b"),
    ]
    with pytest.raises(ValueError, match="duplicate image_id"):
        parse_ls_export_data(data, task_type=TaskType.CAP)


def test_missing_image_id_or_annotations_raises() -> None:
    bad = _cap_task(image_id="x", caption="a")
    bad["data"].pop("image_id")
    with pytest.raises(ValueError, match="image_id"):
        parse_ls_export_data([bad], task_type=TaskType.CAP)

    empty_ann = _cap_task(image_id="y", caption="a")
    empty_ann["annotations"] = []
    with pytest.raises(ValueError, match="no annotations"):
        parse_ls_export_data([empty_ann], task_type=TaskType.CAP)


def test_export_root_must_be_list() -> None:
    with pytest.raises(ValueError, match="JSON array"):
        parse_ls_export_data({"tasks": []}, task_type=TaskType.CAP)


def test_task_type_control_mismatch_raises() -> None:
    data = [_cap_task(image_id="img-m", caption="c")]
    with pytest.raises(ValueError, match="do not match"):
        parse_ls_export_data(data, task_type=TaskType.DET)


def test_seg_missing_mask_ref_raises() -> None:
    task = _seg_task(image_id="img-s", mask_ref="masks/x.png")
    task["data"].pop("mask_ref")
    with pytest.raises(ValueError, match="mask_ref"):
        parse_ls_export_data([task], task_type=TaskType.SEG)


def test_parse_ls_export_reads_file(tmp_path: Path) -> None:
    payload = [_cap_task(image_id="file-1", caption="from file")]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    results = parse_ls_export(path, task_type=TaskType.CAP)
    assert len(results) == 1
    assert results[0].annotation.caption == "from file"


def test_cancelled_annotation_skipped_for_newer() -> None:
    task = _cap_task(image_id="img-c", caption="kept")
    task["annotations"] = [
        {
            "id": 1,
            "was_cancelled": True,
            "updated_at": "2026-08-12T00:00:00.000000Z",
            "result": [
                {
                    "from_name": "cap_text",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": ["cancelled"]},
                },
                _choice("human_confirmed", "yes"),
            ],
        },
        {
            "id": 2,
            "was_cancelled": False,
            "updated_at": "2026-08-11T00:00:00.000000Z",
            "result": [
                {
                    "from_name": "cap_text",
                    "to_name": "image",
                    "type": "textarea",
                    "value": {"text": ["kept"]},
                },
                _choice("human_confirmed", "yes"),
                _choice("needs_rework", "no"),
            ],
        },
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == "kept"


@pytest.mark.skipif(
    not (_LS_EXPORT_ROOT / "cap").exists(),
    reason="demo_batch LS export not present under data/",
)
def test_real_demo_exports_smoke() -> None:
    cap_files = list((_LS_EXPORT_ROOT / "cap").glob("*.json"))
    det_files = list((_LS_EXPORT_ROOT / "det").glob("*.json"))
    seg_files = list((_LS_EXPORT_ROOT / "seg").glob("*.json"))
    assert cap_files and det_files and seg_files

    cap = parse_ls_export(cap_files[0], task_type=TaskType.CAP)
    assert len(cap) == 2
    assert {r.image_id for r in cap} == {
        "demo_batch__000001",
        "demo_batch__000002",
    }
    by_id = {r.image_id: r for r in cap}
    assert by_id["demo_batch__000001"].needs_rework is False
    assert by_id["demo_batch__000002"].needs_rework is True

    # Demo DET uses 1x1 placeholder images in LS export; caller supplies size.
    det_meta = {
        "demo_batch__000001": ImageMetadata(width=1, height=1),
        "demo_batch__000002": ImageMetadata(width=1, height=1),
    }
    det = parse_ls_export(
        det_files[0],
        task_type=TaskType.DET,
        image_metadata_by_id=det_meta,
    )
    assert len(det) == 2
    det_by_id = {r.image_id: r for r in det}
    assert isinstance(det_by_id["demo_batch__000001"].annotation, DetAnnotation)
    assert len(det_by_id["demo_batch__000001"].annotation.bboxes) == 2
    assert det_by_id["demo_batch__000002"].annotation.bboxes == ()

    seg = parse_ls_export(seg_files[0], task_type=TaskType.SEG)
    assert len(seg) == 2
    seg_by_id = {r.image_id: r for r in seg}
    assert seg_by_id["demo_batch__000001"].annotation.mask_ref == (
        "masks/demo_batch__000001.png"
    )
