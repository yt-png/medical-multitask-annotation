"""Tests for rework LS import task builder (T4.3 / S2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import write_json
from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.importers import REWORK_MODEL_VERSION, build_rework_ls_tasks


def _write_package(
    data_root: Path,
    *,
    batch_id: str,
    task: str,
    samples: list[tuple[str, str]],
) -> None:
    package_dir = data_root / "task_packages" / batch_id / task
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_samples = []
    for image_id, diagnosis in samples:
        img_path = images_dir / f"{image_id}.jpg"
        Image.new("RGB", (8, 8), color=(10, 20, 30)).save(img_path)
        manifest_samples.append(
            {
                "image_id": image_id,
                "image_path": f"images/{image_id}.jpg",
                "diagnosis_text": diagnosis,
            }
        )
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{batch_id}__{task}",
            "task_type": task.upper(),
            "batch_id": batch_id,
            "samples": manifest_samples,
        },
    )


def _seg_result(image_id: str, *, needs_rework: bool = True) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=f"masks/{image_id}.png"),
        human_confirmed=True,
        needs_rework=needs_rework,
    )


def _cap_result(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="should-not-be-used"),
        human_confirmed=True,
        needs_rework=True,
    )


def _det_result(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=True,
        needs_rework=True,
    )


def test_build_rework_seg_uses_raw_rle_and_strips_choices(tmp_path: Path) -> None:
    batch_id = "rw_batch"
    image_id = "rw_batch__000001"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="seg",
        samples=[(image_id, "diag from manifest")],
    )
    raw = {
        image_id: (
            {
                "from_name": "seg_mask",
                "type": "brushlabels",
                "value": {
                    "format": "rle",
                    "rle": [9, 8, 7],
                    "brushlabels": ["lesion"],
                },
            },
            {
                "from_name": "human_confirmed",
                "type": "choices",
                "value": {"choices": ["yes"]},
            },
            {
                "from_name": "needs_rework",
                "type": "choices",
                "value": {"choices": ["yes"]},
            },
        )
    }
    tasks = build_rework_ls_tasks(
        [_seg_result(image_id)],
        raw_results_by_image_id=raw,
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    assert len(tasks) == 1
    task = tasks[0]
    assert task["id"] == image_id
    assert task["data"]["diagnosis_text"] == "diag from manifest"
    assert task["data"]["package_id"] == f"{batch_id}__seg"
    assert task["data"]["mask_ref"] == f"masks/{image_id}.png"
    assert task["data"]["image"].startswith("/data/local-files/?d=")
    assert image_id in task["data"]["image"]

    pred = task["predictions"][0]
    assert pred["model_version"] == REWORK_MODEL_VERSION
    assert len(pred["result"]) == 1
    assert pred["result"][0]["value"]["rle"] == [9, 8, 7]
    from_names = {r["from_name"] for r in pred["result"]}
    assert from_names == {"seg_mask"}


def test_build_rework_cap_and_det_use_raw_not_annotation(tmp_path: Path) -> None:
    batch_id = "rw_batch2"
    cap_id = "img-cap"
    det_id = "img-det"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(cap_id, "cap diag")],
    )
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="det",
        samples=[(det_id, "det diag")],
    )

    cap_tasks = build_rework_ls_tasks(
        [_cap_result(cap_id)],
        raw_results_by_image_id={
            cap_id: (
                {
                    "from_name": "cap_text",
                    "type": "textarea",
                    "value": {"text": ["raw caption wins"]},
                },
            )
        },
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert cap_tasks[0]["predictions"][0]["result"][0]["value"]["text"] == [
        "raw caption wins"
    ]

    det_tasks = build_rework_ls_tasks(
        [_det_result(det_id)],
        raw_results_by_image_id={
            det_id: (
                {
                    "from_name": "det_bbox",
                    "type": "rectanglelabels",
                    "value": {
                        "x": 10.0,
                        "y": 20.0,
                        "width": 5.0,
                        "height": 5.0,
                        "rectanglelabels": ["object"],
                    },
                },
            )
        },
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    box = det_tasks[0]["predictions"][0]["result"][0]["value"]
    assert box["x"] == 10.0
    assert box["rectanglelabels"] == ["object"]


def test_missing_raw_side_channel_raises(tmp_path: Path) -> None:
    batch_id = "rw_miss"
    image_id = "img-miss"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(image_id, "diag")],
    )
    with pytest.raises(ValueError, match="missing raw LS result"):
        build_rework_ls_tasks(
            [_cap_result(image_id)],
            raw_results_by_image_id={},
            batch_id=batch_id,
            task_type=TaskType.CAP,
            data_root=tmp_path,
        )


def test_empty_rework_results(tmp_path: Path) -> None:
    tasks = build_rework_ls_tasks(
        (),
        raw_results_by_image_id={},
        batch_id="any_batch",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert tasks == []
