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
    brush_rle: list[int] | None = None,
    original_width: int = 2,
    original_height: int = 2,
) -> dict:
    results: list[dict] = []
    if include_brush:
        rle = brush_rle if brush_rle is not None else [0, 1, 2]
        results.append(
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "original_width": original_width,
                "original_height": original_height,
                "value": {
                    "format": "rle",
                    "rle": rle,
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


def _cap_prediction_result(caption: str) -> dict:
    return {
        "from_name": "cap_text",
        "to_name": "image",
        "type": "textarea",
        "value": {"text": [caption]},
    }


def test_cap_human_overrides_prediction() -> None:
    task = _cap_task(image_id="img-over", caption="A large nodule")
    task["predictions"] = [
        {"result": [_cap_prediction_result("A small nodule")]},
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == "A large nodule"


def test_cap_human_empty_clears_prediction() -> None:
    task = _cap_task(image_id="img-clear", caption="")
    for entry in task["annotations"][0]["result"]:
        if entry.get("from_name") == "cap_text":
            entry["value"]["text"] = [""]
            break
    task["predictions"] = [
        {"result": [_cap_prediction_result("A small nodule")]},
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == ""


def test_cap_missing_textarea_yields_empty() -> None:
    task = _cap_task(image_id="img-no-textarea", caption="ignored")
    task["annotations"][0]["result"] = [
        entry
        for entry in task["annotations"][0]["result"]
        if entry.get("from_name") != "cap_text"
    ]
    task["predictions"] = [
        {"result": [_cap_prediction_result("older")]},
        {"result": [_cap_prediction_result("A small nodule")]},
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == ""


def test_cap_missing_textarea_without_predictions_yields_empty() -> None:
    task = _cap_task(image_id="img-missing", caption="x")
    task["annotations"][0]["result"] = [
        entry
        for entry in task["annotations"][0]["result"]
        if entry.get("from_name") != "cap_text"
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == ""


def test_cap_confirm_only_yields_empty_caption() -> None:
    """Confirm-only: choices only → empty caption (no prediction fill)."""

    task = _cap_task(image_id="img-cap-confirm", caption="ignored")
    task["annotations"][0]["result"] = [
        entry
        for entry in task["annotations"][0]["result"]
        if entry.get("from_name") != "cap_text"
    ]
    task["annotations"][0]["prediction"] = None
    task["predictions"] = [
        {"result": [_cap_prediction_result("肺炎")]},
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == ""


def test_cap_human_cleared_does_not_fall_back_to_prediction() -> None:
    """Accept-then-clear: prediction link set, no cap_text → empty, not prediction."""

    task = _cap_task(image_id="img-cap-cleared", caption="ignored")
    task["annotations"][0]["result"] = [
        entry
        for entry in task["annotations"][0]["result"]
        if entry.get("from_name") != "cap_text"
    ]
    task["annotations"][0]["prediction"] = 42
    task["predictions"] = [
        {"result": [_cap_prediction_result("肺炎")]},
    ]
    results = parse_ls_export_data([task], task_type=TaskType.CAP)
    assert results[0].annotation.caption == ""


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


def _det_prediction_box(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict:
    return {
        "from_name": "det_bbox",
        "to_name": "image",
        "type": "rectanglelabels",
        "value": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "rectanglelabels": ["object"],
        },
    }


def test_parse_det_confirm_only_empty_boxes() -> None:
    """No det_bbox in annotation → empty boxes (predictions ignored)."""

    task = _det_task(image_id="img-det-fb", boxes_pct=[])
    task["predictions"] = [
        {
            "id": 42,
            "result": [
                _det_prediction_box(
                    x=10.0,
                    y=20.0,
                    width=5.0,
                    height=8.0,
                )
            ],
        }
    ]
    meta = {"img-det-fb": ImageMetadata(width=100, height=100)}
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.DET,
        image_metadata_by_id=meta,
    )
    annotation = results[0].annotation
    assert isinstance(annotation, DetAnnotation)
    assert annotation.bboxes == ()


def test_parse_det_ignores_prediction_history() -> None:
    """Multiple predictions must not fill DET boxes when annotation has none."""

    task = _det_task(image_id="img-det-latest", boxes_pct=[])
    task["predictions"] = [
        {
            "id": 1,
            "result": [
                _det_prediction_box(x=10.0, y=20.0, width=5.0, height=8.0),
            ],
        },
        {
            "id": 2,
            "result": [
                _det_prediction_box(x=30.0, y=40.0, width=6.0, height=7.0),
            ],
        },
    ]
    meta = {"img-det-latest": ImageMetadata(width=100, height=100)}
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.DET,
        image_metadata_by_id=meta,
    )
    assert results[0].annotation.bboxes == ()


def test_parse_det_annotation_boxes_preferred_over_predictions() -> None:
    """Case2: annotation has det_bbox → use human boxes (ignore predictions)."""

    task = _det_task(
        image_id="img-det-human",
        boxes_pct=[(50.0, 40.0, 10.0, 12.0)],
    )
    task["predictions"] = [
        {
            "id": 7,
            "result": [
                _det_prediction_box(
                    x=1.0,
                    y=2.0,
                    width=3.0,
                    height=4.0,
                )
            ],
        }
    ]
    meta = {"img-det-human": ImageMetadata(width=100, height=100)}
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.DET,
        image_metadata_by_id=meta,
    )
    annotation = results[0].annotation
    assert isinstance(annotation, DetAnnotation)
    assert len(annotation.bboxes) == 1
    box = annotation.bboxes[0]
    assert box.x == pytest.approx(50.0)
    assert box.y == pytest.approx(40.0)
    assert box.width == pytest.approx(10.0)
    assert box.height == pytest.approx(12.0)


def test_parse_det_cleared_after_accept_yields_empty_boxes() -> None:
    """Case3: no det_bbox but annotation.prediction set → empty (not prediction)."""

    task = _det_task(image_id="img-det-cleared", boxes_pct=[])
    task["annotations"][0]["prediction"] = 42
    task["predictions"] = [
        {
            "id": 42,
            "result": [
                _det_prediction_box(
                    x=10.0,
                    y=20.0,
                    width=5.0,
                    height=8.0,
                )
            ],
        }
    ]
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.DET,
        image_metadata_by_id={"img-det-cleared": ImageMetadata(width=100, height=100)},
    )
    annotation = results[0].annotation
    assert isinstance(annotation, DetAnnotation)
    assert annotation.bboxes == ()


def test_parse_seg_without_manual_dir_raises() -> None:
    data = [
        _seg_task(
            image_id="img-seg-1",
            mask_ref="masks/img-seg-1.png",
            include_brush=True,
        )
    ]
    with pytest.raises(ValueError, match="seg_manual_mask_dir"):
        parse_ls_export_data(data, task_type=TaskType.SEG)


def test_parse_seg_confirm_only_writes_empty_manual(tmp_path: Path) -> None:
    """No SEG geometry: write empty manual mask; ignore predictions / data.mask_ref."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    data = [
        _seg_task(
            image_id="img-seg-nb",
            mask_ref="masks/prelabel.png",
            include_brush=False,
        )
    ]
    data[0]["predictions"] = [
        {
            "id": 10,
            "result": [
                {
                    "from_name": "seg_mask",
                    "to_name": "image",
                    "type": "brushlabels",
                    "original_width": 2,
                    "original_height": 2,
                    "value": {
                        "format": "rle",
                        "rle": [0, 1, 2],
                        "brushlabels": ["lesion"],
                    },
                }
            ],
        }
    ]
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        data,
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
        image_metadata_by_id={
            "img-seg-nb": ImageMetadata(width=2, height=2)
        },
    )
    annotation = results[0].annotation
    assert isinstance(annotation, SegAnnotation)
    assert annotation.mask_ref == manual_mask_ref("img-seg-nb")
    assert annotation.has_foreground is False
    loaded, width, height = load_foreground_mask(
        mask_dir / "img-seg-nb_manual.png"
    )
    assert (width, height) == (2, 2)
    assert loaded == [[0, 0], [0, 0]]


def test_parse_seg_cleared_brushes_writes_empty_mask(tmp_path: Path) -> None:
    """Accepted prediction then deleted all brushes → empty human mask."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    task = _seg_task(
        image_id="img-cleared",
        mask_ref="masks/prelabel.png",
        include_brush=False,
    )
    task["annotations"][0]["prediction"] = 10
    task["predictions"] = [
        {
            "id": 10,
            "result": [
                {
                    "from_name": "seg_mask",
                    "to_name": "image",
                    "type": "brushlabels",
                    "original_width": 3,
                    "original_height": 2,
                    "value": {
                        "format": "rle",
                        "rle": [0, 1, 2],
                        "brushlabels": ["lesion"],
                    },
                }
            ],
        }
    ]
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
        image_metadata_by_id={
            "img-cleared": ImageMetadata(width=3, height=2)
        },
    )
    annotation = results[0].annotation
    assert isinstance(annotation, SegAnnotation)
    assert annotation.mask_ref == manual_mask_ref("img-cleared")
    assert annotation.has_foreground is False
    out_file = mask_dir / "img-cleared_manual.png"
    assert out_file.is_file()
    loaded, width, height = load_foreground_mask(out_file)
    assert (width, height) == (3, 2)
    assert loaded == [[0, 0, 0], [0, 0, 0]]


def test_parse_seg_cleared_via_empty_rle_marker_writes_empty_mask(
    tmp_path: Path,
) -> None:
    """Case 2b: explicit empty ``seg_mask`` rle marker → empty human mask."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    task = _seg_task(
        image_id="img-empty-rle",
        mask_ref="masks/prelabel.png",
        include_brush=False,
    )
    # Insert clear marker before choices
    task["annotations"][0]["result"].insert(
        0,
        {
            "from_name": "seg_mask",
            "to_name": "image",
            "type": "brushlabels",
            "original_width": 2,
            "original_height": 2,
            "value": {
                "format": "rle",
                "rle": [],
                "brushlabels": [],
            },
        },
    )
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
    )
    assert results[0].annotation.mask_ref == manual_mask_ref("img-empty-rle")
    assert results[0].annotation.has_foreground is False
    loaded, width, height = load_foreground_mask(
        mask_dir / "img-empty-rle_manual.png"
    )
    assert (width, height) == (2, 2)
    assert loaded == [[0, 0], [0, 0]]


def test_parse_seg_with_brush_and_manual_dir_writes_mask(tmp_path: Path) -> None:
    """Case 3: annotation has brush → write human mask."""

    from mma.converters.seg_brush import (
        load_foreground_mask,
        manual_mask_ref,
        mask_to_ls_rle,
    )

    binary = [
        [0, 1],
        [1, 0],
    ]
    rle = mask_to_ls_rle(binary)
    data = [
        _seg_task(
            image_id="img-manual",
            mask_ref="masks/old.png",
            brush_rle=rle,
            original_width=2,
            original_height=2,
        )
    ]
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        data,
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
    )
    annotation = results[0].annotation
    assert isinstance(annotation, SegAnnotation)
    assert annotation.mask_ref == manual_mask_ref("img-manual")
    assert annotation.has_foreground is True
    out_file = mask_dir / "img-manual_manual.png"
    assert out_file.is_file()
    loaded, width, height = load_foreground_mask(out_file)
    assert (width, height) == (2, 2)
    assert loaded == binary
    # Must not touch a prelabel path under the same tree
    assert not (tmp_path / "masks" / "old.png").exists()


def test_parse_seg_with_polygon_and_manual_dir_writes_mask(tmp_path: Path) -> None:
    """Case 3b: annotation has polygonlabels → write human mask PNG."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    data = [
        {
            "data": {
                "image": "/data/local-files/?d=x.png",
                "mask_ref": "masks/pre.png",
                "diagnosis_text": "d",
                "image_id": "img-poly",
                "package_id": "pkg",
                "batch_id": "b",
            },
            "annotations": [
                {
                    "result": [
                        {
                            "from_name": "seg_mask",
                            "to_name": "image",
                            "type": "polygonlabels",
                            "original_width": 40,
                            "original_height": 40,
                            "value": {
                                "points": [
                                    [25.0, 25.0],
                                    [75.0, 25.0],
                                    [75.0, 75.0],
                                    [25.0, 75.0],
                                ],
                                "polygonlabels": ["lesion"],
                            },
                        },
                        _choice("human_confirmed", "yes"),
                        _choice("needs_rework", "no"),
                    ]
                }
            ],
        }
    ]
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        data,
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
    )
    annotation = results[0].annotation
    assert isinstance(annotation, SegAnnotation)
    assert annotation.mask_ref == manual_mask_ref("img-poly")
    assert annotation.has_foreground is True
    out_file = mask_dir / "img-poly_manual.png"
    assert out_file.is_file()
    loaded, width, height = load_foreground_mask(out_file)
    assert (width, height) == (40, 40)
    assert sum(sum(row) for row in loaded) > 0


def test_parse_seg_cleared_polygon_writes_empty_mask(tmp_path: Path) -> None:
    """Empty points clear marker → empty human mask."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    data = [
        {
            "data": {
                "image": "/data/local-files/?d=x.png",
                "mask_ref": "masks/pre.png",
                "diagnosis_text": "d",
                "image_id": "img-empty-poly",
                "package_id": "pkg",
                "batch_id": "b",
            },
            "annotations": [
                {
                    "result": [
                        {
                            "from_name": "seg_mask",
                            "to_name": "image",
                            "type": "polygonlabels",
                            "original_width": 3,
                            "original_height": 2,
                            "value": {
                                "points": [],
                                "polygonlabels": [],
                            },
                        },
                        _choice("human_confirmed", "yes"),
                        _choice("needs_rework", "no"),
                    ]
                }
            ],
        }
    ]
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        data,
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
    )
    assert results[0].annotation.mask_ref == manual_mask_ref("img-empty-poly")
    assert results[0].annotation.has_foreground is False
    loaded, width, height = load_foreground_mask(
        mask_dir / "img-empty-poly_manual.png"
    )
    assert (width, height) == (3, 2)
    assert loaded == [[0, 0, 0], [0, 0, 0]]


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


def test_parse_seg_no_mask_ref_ok_with_manual_dir(tmp_path: Path) -> None:
    """V1: missing data.mask_ref is fine when manual dir + metadata are provided."""

    from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref

    task = _seg_task(
        image_id="img-s",
        mask_ref="masks/x.png",
        include_brush=False,
    )
    task["data"].pop("mask_ref")
    mask_dir = tmp_path / "manual_masks"
    results = parse_ls_export_data(
        [task],
        task_type=TaskType.SEG,
        seg_manual_mask_dir=mask_dir,
        image_metadata_by_id={"img-s": ImageMetadata(width=2, height=2)},
    )
    assert results[0].annotation.mask_ref == manual_mask_ref("img-s")
    loaded, width, height = load_foreground_mask(mask_dir / "img-s_manual.png")
    assert (width, height) == (2, 2)
    assert loaded == [[0, 0], [0, 0]]


def test_parse_without_predictions_key_ok_for_cap_det_seg(tmp_path: Path) -> None:
    """No predictions key: CAP/DET/SEG still parse (V1 empty-task exports)."""

    from mma.converters.seg_brush import manual_mask_ref

    cap = _cap_task(image_id="img-np-cap", caption="hello")
    assert "predictions" not in cap
    cap_results = parse_ls_export_data([cap], task_type=TaskType.CAP)
    assert cap_results[0].annotation.caption == "hello"

    det = _det_task(image_id="img-np-det", boxes_pct=[(10.0, 20.0, 5.0, 5.0)])
    assert "predictions" not in det
    det_results = parse_ls_export_data(
        [det],
        task_type=TaskType.DET,
        image_metadata_by_id={
            "img-np-det": ImageMetadata(width=100, height=100)
        },
    )
    assert len(det_results[0].annotation.bboxes) == 1

    seg = _seg_task(
        image_id="img-np-seg",
        mask_ref="masks/x.png",
        include_brush=False,
    )
    seg["data"].pop("mask_ref")
    assert "predictions" not in seg
    seg_results = parse_ls_export_data(
        [seg],
        task_type=TaskType.SEG,
        seg_manual_mask_dir=tmp_path / "manual_masks",
        image_metadata_by_id={
            "img-np-seg": ImageMetadata(width=2, height=2)
        },
    )
    assert seg_results[0].annotation.mask_ref == manual_mask_ref("img-np-seg")


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
def test_real_demo_exports_smoke(tmp_path: Path) -> None:
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

    seg = parse_ls_export(
        seg_files[0],
        task_type=TaskType.SEG,
        seg_manual_mask_dir=tmp_path / "manual_masks",
        image_metadata_by_id={
            "demo_batch__000001": ImageMetadata(width=1, height=1),
            "demo_batch__000002": ImageMetadata(width=1, height=1),
        },
    )
    assert len(seg) == 2
    seg_by_id = {r.image_id: r for r in seg}
    from mma.converters.seg_brush import manual_mask_ref

    assert seg_by_id["demo_batch__000001"].annotation.mask_ref == (
        manual_mask_ref("demo_batch__000001")
    )
