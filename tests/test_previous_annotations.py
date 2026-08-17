"""Tests for self-contained rework previous_annotations + rework-import."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import (
    results_manual_masks_dir,
    results_rework_dir,
)
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.exporters import previous_annotations as previous_annotations_mod
from mma.exporters.previous_annotations import (
    build_ls_prediction_results_from_previous,
    previous_annotations_json_path,
    write_previous_annotations,
)
from mma.exporters.refresh_normal_rework import write_normal_rework_bundles
from mma.importers import rework_import_from_export


def test_module_doc_states_previous_ne_prediction() -> None:
    """M6.4: module docs nail previous_annotations ≠ model prediction."""

    doc = previous_annotations_mod.__doc__ or ""
    assert "previous_annotations" in doc
    assert "≠ prediction" in doc or "!= prediction" in doc
    assert "human" in doc.lower()
    build_doc = build_ls_prediction_results_from_previous.__doc__ or ""
    assert "previous_annotations" in build_doc
    assert "not model" in build_doc.lower() or "≠ prediction" in build_doc
    assert "M6.1" in build_doc or "gold" in build_doc.lower() or "fallback" in build_doc.lower()


def _write_package(
    data_root: Path,
    *,
    batch_id: str,
    task: str,
    samples: list[tuple[str, str]],
    size: tuple[int, int] = (20, 20),
) -> None:
    package_dir = data_root / "task_packages" / batch_id / task
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest_samples = []
    for image_id, diagnosis in samples:
        Image.new("RGB", size, color=(10, 20, 30)).save(
            images_dir / f"{image_id}.jpg"
        )
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


def _write_seg_mask(
    data_root: Path,
    batch_id: str,
    image_id: str,
    *,
    binary: list[list[int]],
) -> str:
    """Write manual mask; return mask_ref relative to results/.../seg/."""

    from mma.converters.seg_brush import manual_mask_ref

    mask_dir = results_manual_masks_dir(batch_id, data_root=data_root)
    mask_dir.mkdir(parents=True, exist_ok=True)
    h = len(binary)
    w = len(binary[0])
    img = Image.new("L", (w, h))
    img.putdata([255 if v else 0 for row in binary for v in row])
    path = mask_dir / f"{image_id}_manual.png"
    img.save(path)
    return manual_mask_ref(image_id)


def test_write_previous_det_omits_label(tmp_path: Path) -> None:
    """BBox has no label field — snapshot must not invent one."""

    batch_id = "prev_det"
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__det",
    )
    path = write_previous_annotations(
        [item],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    payload = read_json(path)
    assert payload[0]["image_id"] == "img-1"
    box = payload[0]["bboxes"][0]
    assert box == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}
    assert "label" not in box


def test_rework_import_from_previous_without_export(tmp_path: Path) -> None:
    """A: only rework/ (+ previous_annotations), no ls_export → success."""

    batch_id = "self_rw"
    det_id = "img-det"
    cap_id = "img-cap"
    seg_id = "img-seg"
    _write_package(
        tmp_path, batch_id=batch_id, task="det", samples=[(det_id, "d")]
    )
    _write_package(
        tmp_path, batch_id=batch_id, task="cap", samples=[(cap_id, "c")]
    )
    _write_package(
        tmp_path, batch_id=batch_id, task="seg", samples=[(seg_id, "s")]
    )

    mask_ref = _write_seg_mask(
        tmp_path,
        batch_id,
        seg_id,
        binary=[
            [0, 0, 0, 0],
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 0],
        ],
    )

    det_item = TaskAnnotationResult(
        image_id=det_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=2.0, y=4.0, width=6.0, height=8.0),)
        ),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__det",
    )
    cap_item = TaskAnnotationResult(
        image_id=cap_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="previous caption text"),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    seg_item = TaskAnnotationResult(
        image_id=seg_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=mask_ref),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__seg",
    )

    write_normal_rework_bundles(
        (),
        (det_item,),
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    write_normal_rework_bundles(
        (),
        (cap_item,),
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    write_normal_rework_bundles(
        (),
        (seg_item,),
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )

    assert previous_annotations_json_path(
        batch_id, TaskType.DET, data_root=tmp_path
    ).is_file()
    seg_prev = read_json(
        previous_annotations_json_path(
            batch_id, TaskType.SEG, data_root=tmp_path
        )
    )
    assert seg_prev[0]["mask_file"].startswith("masks/")
    assert (
        results_rework_dir(batch_id, TaskType.SEG, data_root=tmp_path)
        / "previous_annotations"
        / seg_prev[0]["mask_file"]
    ).is_file()
    assert isinstance(seg_prev[0]["polygons"], list)
    assert len(seg_prev[0]["polygons"]) >= 1

    # No export path — must succeed via previous_annotations
    det_out = rework_import_from_export(
        None,
        batch_id=batch_id,
        task="det",
        data_root=tmp_path,
    )
    cap_out = rework_import_from_export(
        None,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    seg_out = rework_import_from_export(
        None,
        batch_id=batch_id,
        task="seg",
        data_root=tmp_path,
    )

    det_tasks = read_json(det_out)
    cap_tasks = read_json(cap_out)
    seg_tasks = read_json(seg_out)

    # B: predictions contain rectanglelabels / polygonlabels / textarea
    det_result = det_tasks[0]["predictions"][0]["result"]
    assert det_result
    assert det_result[0]["type"] == "rectanglelabels"
    assert "rectanglelabels" in det_result[0]["value"]
    assert det_result[0]["value"]["rectanglelabels"] == ["object"]
    # pixel (2,4,6,8) on 20x20 → percent
    assert det_result[0]["value"]["x"] == pytest.approx(10.0)
    assert det_result[0]["value"]["y"] == pytest.approx(20.0)

    cap_result = cap_tasks[0]["predictions"][0]["result"]
    assert cap_result[0]["type"] == "textarea"
    assert cap_result[0]["value"]["text"] == ["previous caption text"]

    seg_result = seg_tasks[0]["predictions"][0]["result"]
    assert seg_result
    assert seg_result[0]["type"] == "polygonlabels"
    assert "points" in seg_result[0]["value"]
    assert len(seg_result[0]["value"]["points"]) >= 3


def test_rework_import_legacy_export_without_previous(tmp_path: Path) -> None:
    """C-compat: delete previous_annotations, --export still works."""

    batch_id = "legacy_rw"
    image_id = "img-a"
    _write_package(
        tmp_path, batch_id=batch_id, task="cap", samples=[(image_id, "diag")]
    )

    # annotations only — no previous_annotations dir
    rework_dir = results_rework_dir(batch_id, TaskType.CAP, data_root=tmp_path)
    rework_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        rework_dir / ANNOTATIONS_JSON_NAME,
        [
            {
                "image_id": image_id,
                "task_type": "CAP",
                "annotation": {"caption": "from-current"},
                "human_confirmed": True,
                "needs_rework": True,
                "package_id": f"{batch_id}__cap",
                "export_round": None,
            }
        ],
    )

    export = tmp_path / "export.json"
    write_json(
        export,
        [
            {
                "data": {
                    "image_id": image_id,
                    "package_id": f"{batch_id}__cap",
                    "diagnosis_text": "diag",
                },
                "annotations": [
                    {
                        "id": 1,
                        "was_cancelled": False,
                        "updated_at": "2026-08-11T00:00:00.000000Z",
                        "result": [
                            {
                                "from_name": "cap_text",
                                "to_name": "image",
                                "type": "textarea",
                                "value": {"text": ["from-export-raw"]},
                            },
                            {
                                "from_name": "human_confirmed",
                                "to_name": "image",
                                "type": "choices",
                                "value": {"choices": ["yes"]},
                            },
                            {
                                "from_name": "needs_rework",
                                "to_name": "image",
                                "type": "choices",
                                "value": {"choices": ["yes"]},
                            },
                        ],
                    }
                ],
            }
        ],
    )

    assert not previous_annotations_json_path(
        batch_id, TaskType.CAP, data_root=tmp_path
    ).is_file()

    out = rework_import_from_export(
        export,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    tasks = read_json(out)
    assert tasks[0]["predictions"][0]["result"][0]["value"]["text"] == [
        "from-export-raw"
    ]


def test_rework_import_missing_previous_and_export_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="previous_annotations is missing"):
        rework_import_from_export(
            None,
            batch_id="no_prev",
            task="cap",
            data_root=tmp_path,
        )


def test_apply_current_overwrite_unaffected_with_previous(
    tmp_path: Path,
) -> None:
    """C: after previous_annotations exist, apply-current merge still works."""

    from mma.exporters import apply_current_from_export, load_current

    batch_id = "ov_batch"
    image_id = "img-a"
    _write_package(
        tmp_path, batch_id=batch_id, task="cap", samples=[(image_id, "diag")]
    )

    item = TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="old"),
        human_confirmed=True,
        needs_rework=True,
        package_id=f"{batch_id}__cap",
    )
    write_normal_rework_bundles(
        (),
        (item,),
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert previous_annotations_json_path(
        batch_id, TaskType.CAP, data_root=tmp_path
    ).is_file()

    export = tmp_path / "round2.json"
    write_json(
        export,
        [
            {
                "data": {
                    "image_id": image_id,
                    "package_id": f"{batch_id}__cap",
                    "diagnosis_text": "diag",
                },
                "annotations": [
                    {
                        "id": 2,
                        "was_cancelled": False,
                        "updated_at": "2026-08-12T00:00:00.000000Z",
                        "result": [
                            {
                                "from_name": "cap_text",
                                "to_name": "image",
                                "type": "textarea",
                                "value": {"text": ["fixed"]},
                            },
                            {
                                "from_name": "human_confirmed",
                                "to_name": "image",
                                "type": "choices",
                                "value": {"choices": ["yes"]},
                            },
                            {
                                "from_name": "needs_rework",
                                "to_name": "image",
                                "type": "choices",
                                "value": {"choices": ["no"]},
                            },
                        ],
                    }
                ],
            }
        ],
    )
    apply_current_from_export(
        export,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    loaded = load_current(batch_id, TaskType.CAP, data_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].annotation.caption == "fixed"
    assert loaded[0].needs_rework is False
    # rework emptied; previous snapshot refreshed to []
    assert read_json(
        previous_annotations_json_path(
            batch_id, TaskType.CAP, data_root=tmp_path
        )
    ) == []
