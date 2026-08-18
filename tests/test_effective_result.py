"""Tests for resolve_effective_result (V1: annotation-only effective)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import write_json
from mma.common.models import TaskType
from mma.converters import ImageMetadata
from mma.converters.to_labelstudio import DEFAULT_LS_RESULT_SPECS
from mma.exporters.effective_result import resolve_effective_result
from mma.exporters.extract_ls_raw_results import extract_ls_raw_results_data
from mma.exporters.parse_ls_export import parse_ls_export_data
from mma.exporters.split_by_rework import split_by_rework
from mma.importers.build_rework_tasks import build_rework_ls_tasks


def _choice(from_name: str, value: str = "yes") -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _det_box(x: float = 10.0, y: float = 20.0) -> dict:
    return {
        "from_name": "det_bbox",
        "to_name": "image",
        "type": "rectanglelabels",
        "original_width": 100,
        "original_height": 100,
        "value": {
            "x": x,
            "y": y,
            "width": 5.0,
            "height": 5.0,
            "rectanglelabels": ["object"],
        },
    }


def _cap_text(text: str) -> dict:
    return {
        "from_name": "cap_text",
        "to_name": "image",
        "type": "textarea",
        "value": {"text": [text]},
    }


def _seg_poly(points: list[list[float]] | None = None) -> dict:
    return {
        "from_name": "seg_mask",
        "to_name": "image",
        "type": "polygonlabels",
        "original_width": 10,
        "original_height": 10,
        "value": {
            "points": points
            or [[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]],
            "polygonlabels": ["lesion"],
        },
    }


def _task(
    *,
    image_id: str,
    ann_result: list[dict],
    predictions: list[dict] | None = None,
    prediction_link: int | None = None,
) -> dict:
    ann: dict = {
        "id": 1,
        "was_cancelled": False,
        "updated_at": "2026-08-11T00:00:00.000000Z",
        "result": ann_result,
        "prediction": prediction_link,
    }
    task: dict = {
        "data": {"image_id": image_id, "package_id": "pkg", "mask_ref": "masks/x.png"},
        "annotations": [ann],
    }
    if predictions is not None:
        task["predictions"] = predictions
    return task


def _task_control(task_type: TaskType) -> str:
    return DEFAULT_LS_RESULT_SPECS[task_type]["from_name"]


def test_human_edit_overrides_prediction() -> None:
    task = _task(
        image_id="img-edit",
        ann_result=[
            _det_box(1.0, 2.0),
            _choice("human_confirmed", "yes"),
            _choice("needs_rework", "no"),
        ],
        predictions=[{"result": [_det_box(90.0, 90.0)]}],
    )
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-edit"
    )
    assert effective.source == "annotation"
    boxes = [
        e for e in effective.effective_result if e.get("from_name") == "det_bbox"
    ]
    assert len(boxes) == 1
    assert boxes[0]["value"]["x"] == 1.0
    # Predictions may still be traced but must not replace human effective.
    pred_boxes = [
        e for e in effective.prediction_result if e.get("from_name") == "det_bbox"
    ]
    assert len(pred_boxes) == 1
    assert pred_boxes[0]["value"]["x"] == 90.0


def test_confirm_only_does_not_use_prediction() -> None:
    task = _task(
        image_id="img-confirm",
        ann_result=[
            _choice("human_confirmed", "yes"),
            _choice("needs_rework", "yes"),
        ],
        predictions=[
            {
                "result": [
                    _det_box(10.0, 20.0),
                ]
            }
        ],
        prediction_link=None,
    )
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-confirm"
    )
    assert effective.source == "empty"
    assert effective.human_cleared is False
    from_names = {e["from_name"] for e in effective.effective_result}
    assert "det_bbox" not in from_names
    assert "human_confirmed" in from_names
    pred_boxes = [
        e for e in effective.prediction_result if e.get("from_name") == "det_bbox"
    ]
    assert len(pred_boxes) == 1


def test_human_cleared_no_prediction_in_effective() -> None:
    task = _task(
        image_id="img-clear",
        ann_result=[
            _choice("human_confirmed", "yes"),
            _choice("needs_rework", "no"),
        ],
        predictions=[{"result": [_det_box(10.0, 20.0)]}],
        prediction_link=42,
    )
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-clear"
    )
    assert effective.human_cleared is True
    assert effective.source == "empty"
    assert all(e.get("from_name") != "det_bbox" for e in effective.effective_result)


def test_predictions_traced_but_not_effective() -> None:
    """Confirm-only: latest prediction is traced; effective stays annotation-only."""

    task = _task(
        image_id="img-latest",
        ann_result=[
            _choice("human_confirmed", "yes"),
            _choice("needs_rework", "no"),
        ],
        predictions=[
            {"result": [_det_box(1.0, 1.0)]},
            {"result": []},
            {"result": [_det_box(30.0, 40.0)]},
        ],
        prediction_link=None,
    )
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-latest"
    )
    assert effective.source == "empty"
    boxes = [
        e for e in effective.effective_result if e.get("from_name") == "det_bbox"
    ]
    assert boxes == []
    traced = [
        e for e in effective.prediction_result if e.get("from_name") == "det_bbox"
    ]
    assert len(traced) == 1
    assert traced[0]["value"]["x"] == 30.0


def test_parse_confirm_only_yields_empty_det() -> None:
    """parse_ls_export confirm-only does not fill DET boxes from prediction."""

    data = [
        _task(
            image_id="img-p",
            ann_result=[
                _choice("human_confirmed", "yes"),
                _choice("needs_rework", "no"),
            ],
            predictions=[{"result": [_det_box(10.0, 20.0)]}],
        )
    ]
    parsed = parse_ls_export_data(
        data,
        task_type=TaskType.DET,
        image_metadata_by_id={"img-p": ImageMetadata(width=100, height=100)},
    )
    assert parsed[0].annotation.bboxes == ()
    normal, rework = split_by_rework(parsed)
    assert normal == ()
    assert [item.image_id for item in rework] == ["img-p"]


def test_parse_human_cleared_yields_empty_det() -> None:
    """parse_ls_export Accept-then-clear does not fall back to prediction boxes."""

    data = [
        _task(
            image_id="img-hc",
            ann_result=[
                _choice("human_confirmed", "yes"),
                _choice("needs_rework", "no"),
            ],
            predictions=[{"result": [_det_box(10.0, 20.0)]}],
            prediction_link=99,
        )
    ]
    parsed = parse_ls_export_data(
        data,
        task_type=TaskType.DET,
        image_metadata_by_id={"img-hc": ImageMetadata(width=100, height=100)},
    )
    assert parsed[0].annotation.bboxes == ()


def test_extract_confirm_only_excludes_prediction_geometry() -> None:
    data = [
        _task(
            image_id="img-a",
            ann_result=[_choice("human_confirmed", "yes")],
            predictions=[{"result": [_det_box(15.0, 25.0)]}],
        )
    ]
    by_id = extract_ls_raw_results_data(data, task_type=TaskType.DET)
    result = by_id["img-a"]
    boxes = [e for e in result if e.get("from_name") == "det_bbox"]
    assert boxes == []
    assert any(e.get("from_name") == "human_confirmed" for e in result)


def _write_package(
    data_root: Path,
    *,
    batch_id: str,
    task: str,
    image_id: str,
) -> None:
    package_dir = data_root / "task_packages" / batch_id / task
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (100, 100), color=(1, 2, 3)).save(
        images_dir / f"{image_id}.jpg"
    )
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{batch_id}__{task}",
            "task_type": task.upper(),
            "batch_id": batch_id,
            "samples": [
                {
                    "image_id": image_id,
                    "image_path": f"images/{image_id}.jpg",
                    "diagnosis_text": "diag",
                }
            ],
        },
    )


def test_legacy_rework_raw_confirm_only_no_prelabel_geometry(tmp_path: Path) -> None:
    """Legacy raw path: no task-control geometry from predictions in extract/rework.

    CAP confirm-only without ``cap_text`` cannot parse after M6.1 (no fallback);
    use human_cleared so parse yields empty caption while pred text is ignored.
    """

    batch_id = "leg_fb"
    cases: list[tuple[str, str, list[dict], list[dict], TaskType, int | None]] = [
        (
            "det",
            "img-det",
            [_choice("human_confirmed", "yes"), _choice("needs_rework", "yes")],
            [_det_box(10.0, 20.0)],
            TaskType.DET,
            None,
        ),
        (
            "cap",
            "img-cap",
            [_choice("human_confirmed", "yes"), _choice("needs_rework", "yes")],
            [_cap_text("prelabel caption")],
            TaskType.CAP,
            1,
        ),
        (
            "seg",
            "img-seg",
            [_choice("human_confirmed", "yes"), _choice("needs_rework", "yes")],
            [_seg_poly()],
            TaskType.SEG,
            None,
        ),
    ]
    for task, image_id, ann_result, pred_result, task_type, prediction_link in cases:
        _write_package(tmp_path, batch_id=batch_id, task=task, image_id=image_id)
        export_task = _task(
            image_id=image_id,
            ann_result=ann_result,
            predictions=[{"result": pred_result}],
            prediction_link=prediction_link,
        )
        if task == "det":
            results = parse_ls_export_data(
                [export_task],
                task_type=task_type,
                image_metadata_by_id={
                    "img-det": ImageMetadata(width=100, height=100)
                },
            )
        elif task == "seg":
            results = parse_ls_export_data(
                [export_task],
                task_type=task_type,
                seg_manual_mask_dir=tmp_path / "manual_masks",
                image_metadata_by_id={
                    "img-seg": ImageMetadata(width=10, height=10)
                },
            )
        else:
            results = parse_ls_export_data([export_task], task_type=task_type)

        _, rework = split_by_rework(results)
        raw = extract_ls_raw_results_data([export_task], task_type=task_type)
        control = _task_control(task_type)
        assert all(e.get("from_name") != control for e in raw[image_id])

        tasks = build_rework_ls_tasks(
            rework,
            batch_id=batch_id,
            task_type=task_type,
            prediction_source="raw",
            raw_results_by_image_id=raw,
            data_root=tmp_path,
        )
        assert len(tasks) == 1
        pred = tasks[0]["predictions"][0]["result"]
        assert all(e.get("from_name") != control for e in pred)
        assert not any(
            e.get("type") in {"rectanglelabels", "textarea", "polygonlabels"}
            for e in pred
        )


def test_rework_shaped_predictions_do_not_become_effective() -> None:
    """M4.3 × M6.1: rework LS ``predictions`` prefill is not gold standard."""

    task = _task(
        image_id="img-det",
        ann_result=[
            _choice("human_confirmed", "yes"),
            _choice("needs_rework", "no"),
        ],
        predictions=[
            {
                "model_version": "mma-rework-prev-1.0",
                "result": [_det_box(10.0, 20.0)],
            }
        ],
    )
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-det"
    )
    assert effective.source == "empty"
    assert all(
        entry.get("from_name") != "det_bbox" for entry in effective.effective_result
    )


def test_missing_annotations_source_empty_ignores_predictions() -> None:
    task = {
        "data": {"image_id": "img-skip", "package_id": "pkg"},
        "annotations": [],
        "predictions": [{"result": [_det_box(10.0, 20.0)]}],
    }
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-skip"
    )
    assert effective.source == "empty"
    assert effective.effective_result == ()
    assert effective.annotation_result == ()
    traced = [
        e for e in effective.prediction_result if e.get("from_name") == "det_bbox"
    ]
    assert len(traced) == 1


def test_null_annotation_result_source_empty() -> None:
    task = _task(image_id="img-null-result", ann_result=[])
    task["annotations"][0]["result"] = None
    task["predictions"] = [{"result": [_det_box(10.0, 20.0)]}]
    effective = resolve_effective_result(
        task, task_type=TaskType.DET, image_id="img-null-result"
    )
    assert effective.source == "empty"
    assert effective.effective_result == ()
    assert all(
        entry.get("from_name") != "det_bbox" for entry in effective.effective_result
    )
