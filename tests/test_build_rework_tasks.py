"""Tests for rework LS import task builder (T4.3 / M4.3).

V1 prefill source is ``previous_annotations`` only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import write_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import results_manual_masks_dir
from mma.exporters.previous_annotations import write_previous_annotations
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


def test_empty_rework_results(tmp_path: Path) -> None:
    tasks = build_rework_ls_tasks(
        (),
        batch_id="any_batch",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert tasks == []


def test_default_source_is_previous(tmp_path: Path) -> None:
    batch_id = "rw_default"
    image_id = "img-cap"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(image_id, "diag")],
    )
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="from-previous"),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    pred = tasks[0]["predictions"][0]
    assert pred["model_version"] == REWORK_MODEL_VERSION
    assert pred["result"][0]["value"]["text"] == ["from-previous"]


def test_build_rework_from_previous_cap(tmp_path: Path) -> None:
    batch_id = "rw_prev_cap"
    image_id = "img-cap"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(image_id, "cap diag")],
    )
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="previous caption text"),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert len(tasks) == 1
    pred = tasks[0]["predictions"][0]
    assert pred["model_version"] == REWORK_MODEL_VERSION
    assert pred["result"][0]["from_name"] == "cap_text"
    assert pred["result"][0]["value"]["text"] == ["previous caption text"]


def test_build_rework_from_previous_det(tmp_path: Path) -> None:
    batch_id = "rw_prev_det"
    image_id = "img-det"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="det",
        samples=[(image_id, "det diag")],
    )
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=2.0, height=2.0),)
        ),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__det",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    box = tasks[0]["predictions"][0]["result"][0]
    assert box["type"] == "rectanglelabels"
    # 8x8 package image: pixel (1,2,2,2) → percent (12.5, 25, 25, 25)
    assert box["value"]["x"] == pytest.approx(12.5)
    assert box["value"]["y"] == pytest.approx(25.0)
    assert box["value"]["width"] == pytest.approx(25.0)
    assert box["value"]["height"] == pytest.approx(25.0)
    assert box["value"]["rectanglelabels"] == ["object"]


def test_ignores_orphan_prelabels_json(tmp_path: Path) -> None:
    batch_id = "rw_ignore_pre"
    image_id = "img-cap"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(image_id, "diag")],
    )
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="from-previous"),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    prelabel_dir = tmp_path / "prelabels" / batch_id / "cap"
    prelabel_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        prelabel_dir / "prelabels.json",
        {
            "schema_version": "1.0",
            "task_type": "CAP",
            "items": [
                {
                    "image_id": image_id,
                    "payload": {"caption": "from-prelabel"},
                }
            ],
        },
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    text = tasks[0]["predictions"][0]["result"][0]["value"]["text"]
    assert text == ["from-previous"]
    assert text != ["from-prelabel"]


def test_empty_cap_payload_still_emits_task(tmp_path: Path) -> None:
    batch_id = "rw_empty_cap"
    image_id = "img-cap"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[(image_id, "diag")],
    )
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=""),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert len(tasks) == 1
    pred = tasks[0]["predictions"][0]["result"]
    cap_texts = [
        "".join(entry.get("value", {}).get("text") or [])
        for entry in pred
        if entry.get("from_name") == "cap_text"
    ]
    assert all(not text.strip() for text in cap_texts)


def test_seg_mask_ref_only_from_previous_mask_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mma.converters.seg_brush import manual_mask_ref

    batch_id = "rw_seg_mask"
    image_id = "img-seg"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="seg",
        samples=[(image_id, "seg diag")],
    )
    mask_dir = results_manual_masks_dir(batch_id, data_root=tmp_path)
    mask_dir.mkdir(parents=True, exist_ok=True)
    Image.new("L", (4, 4), color=255).save(mask_dir / f"{image_id}_manual.png")
    mask_ref = manual_mask_ref(image_id)
    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=mask_ref),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__seg",
    )
    write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    tasks = build_rework_ls_tasks(
        [item],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    assert tasks[0]["data"]["mask_ref"].startswith("previous_annotations/")
    assert tasks[0]["data"]["mask_ref"] != mask_ref

    other_id = "img-seg-nomask"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="seg",
        samples=[(image_id, "seg diag"), (other_id, "seg diag 2")],
    )
    annotation_only_ref = f"masks/{other_id}.png"
    other = TaskAnnotationResult(
        image_id=other_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=annotation_only_ref),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__seg",
    )
    prev_dir = (
        tmp_path / "results" / batch_id / "seg" / "rework" / "previous_annotations"
    )
    prev_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        prev_dir / "seg.json",
        [{"image_id": other_id, "polygons": []}],
    )
    monkeypatch.setattr(
        "mma.importers.build_rework_tasks.build_ls_prediction_results_from_previous",
        lambda *args, **kwargs: [],
    )
    tasks_nomask = build_rework_ls_tasks(
        [other],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    assert "mask_ref" not in tasks_nomask[0]["data"]
    assert annotation_only_ref not in str(tasks_nomask[0]["data"])
