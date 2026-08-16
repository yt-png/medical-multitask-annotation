"""Tests for rework_import_from_export (P4 rework-import glue)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.common.paths import ls_import_task_dir
from mma.importers import (
    REWORK_MODEL_VERSION,
    REWORK_TASKS_JSON_NAME,
    TASKS_JSON_NAME,
    rework_import_from_export,
)


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


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
        Image.new("RGB", (8, 8), color=(10, 20, 30)).save(
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


def _cap_task(
    *,
    image_id: str,
    caption: str,
    rework: str = "no",
    package_id: str = "batch1__cap",
) -> dict:
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "diagnosis_text": "ignored-diag",
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
                        "value": {"text": [caption]},
                    },
                    _choice("human_confirmed", "yes"),
                    _choice("needs_rework", rework),
                ],
            }
        ],
    }


def _seg_task(
    *,
    image_id: str,
    mask_ref: str,
    rle: list[int] | None = None,
    rework: str = "yes",
    package_id: str = "batch1__seg",
) -> dict:
    from mma.converters.seg_brush import mask_to_ls_rle

    brush_rle = rle if rle is not None else mask_to_ls_rle([[1, 0], [0, 1]])
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "mask_ref": mask_ref,
            "diagnosis_text": "ignored",
        },
        "annotations": [
            {
                "id": 1,
                "was_cancelled": False,
                "updated_at": "2026-08-11T00:00:00.000000Z",
                "result": [
                    {
                        "from_name": "seg_mask",
                        "to_name": "image",
                        "type": "brushlabels",
                        "original_width": 2,
                        "original_height": 2,
                        "value": {
                            "format": "rle",
                            "rle": brush_rle,
                            "brushlabels": ["lesion"],
                        },
                    },
                    _choice("human_confirmed", "yes"),
                    _choice("needs_rework", rework),
                ],
            }
        ],
    }


def _det_task(
    *,
    image_id: str,
    boxes_pct: list[tuple[float, float, float, float]],
    rework: str = "yes",
    package_id: str = "batch1__det",
) -> dict:
    results: list[dict] = []
    for x, y, w, h in boxes_pct:
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
    results.append(_choice("human_confirmed", "yes"))
    results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
            "diagnosis_text": "ignored",
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


def test_mixed_cap_writes_only_rework_tasks(tmp_path: Path) -> None:
    batch_id = "batch1"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[
            ("img-a", "diag-a"),
            ("img-b", "diag-b"),
        ],
    )
    export = tmp_path / "cap.json"
    write_json(
        export,
        [
            _cap_task(image_id="img-a", caption="ok", rework="no"),
            _cap_task(image_id="img-b", caption="raw wins", rework="yes"),
        ],
    )
    out = rework_import_from_export(
        export,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    expected = (
        ls_import_task_dir(batch_id, TaskType.CAP, data_root=tmp_path)
        / REWORK_TASKS_JSON_NAME
    )
    assert out == expected.resolve()
    tasks = read_json(out)
    assert len(tasks) == 1
    task = tasks[0]
    assert task["id"] == "img-b"
    assert task["data"]["diagnosis_text"] == "diag-b"
    assert task["data"]["image"].startswith("/data/local-files/?d=")
    pred = task["predictions"][0]
    assert pred["model_version"] == REWORK_MODEL_VERSION
    assert pred["result"][0]["value"]["text"] == ["raw wins"]
    from_names = {r["from_name"] for r in pred["result"]}
    assert "human_confirmed" not in from_names
    assert "needs_rework" not in from_names


def test_all_normal_writes_empty_array(tmp_path: Path) -> None:
    batch_id = "batch1"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[("img-a", "diag")],
    )
    export = tmp_path / "cap.json"
    write_json(
        export,
        [_cap_task(image_id="img-a", caption="ok", rework="no")],
    )
    out = rework_import_from_export(
        export,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    assert out.is_file()
    assert read_json(out) == []


def test_seg_keeps_raw_rle_strips_choices(tmp_path: Path) -> None:
    batch_id = "batch1"
    image_id = "img-seg"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="seg",
        samples=[(image_id, "seg diag")],
    )
    export = tmp_path / "seg.json"
    from mma.converters.seg_brush import mask_to_ls_rle

    brush_rle = mask_to_ls_rle([[1, 0], [0, 1]])
    write_json(
        export,
        [
            _seg_task(
                image_id=image_id,
                mask_ref=f"masks/{image_id}.png",
                rle=brush_rle,
                rework="yes",
            )
        ],
    )
    out = rework_import_from_export(
        export,
        batch_id=batch_id,
        task="seg",
        data_root=tmp_path,
    )
    task = read_json(out)[0]
    from mma.converters.seg_brush import manual_mask_ref

    assert task["data"]["mask_ref"] == manual_mask_ref(image_id)
    pred = task["predictions"][0]["result"]
    assert len(pred) == 1
    assert pred[0]["value"]["rle"] == brush_rle


def test_det_builds_with_package_images(tmp_path: Path) -> None:
    batch_id = "batch1"
    image_id = "img-det"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="det",
        samples=[(image_id, "det diag")],
    )
    export = tmp_path / "det.json"
    write_json(
        export,
        [
            _det_task(
                image_id=image_id,
                boxes_pct=[(10.0, 20.0, 5.0, 5.0)],
                rework="yes",
            )
        ],
    )
    out = rework_import_from_export(
        export,
        batch_id=batch_id,
        task="det",
        data_root=tmp_path,
    )
    box = read_json(out)[0]["predictions"][0]["result"][0]["value"]
    assert box["x"] == 10.0
    assert box["rectanglelabels"] == ["object"]


def test_missing_export_and_bad_batch_id(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rework_import_from_export(
            tmp_path / "missing.json",
            batch_id="batch1",
            task="cap",
            data_root=tmp_path,
        )
    _write_package(
        tmp_path,
        batch_id="batch1",
        task="cap",
        samples=[("img-a", "diag")],
    )
    export = tmp_path / "cap.json"
    write_json(export, [_cap_task(image_id="img-a", caption="x", rework="yes")])
    with pytest.raises(ValueError, match="batch_id"):
        rework_import_from_export(
            export,
            batch_id="bad/id",
            task="cap",
            data_root=tmp_path,
        )


def test_does_not_overwrite_existing_tasks_json(tmp_path: Path) -> None:
    batch_id = "batch1"
    _write_package(
        tmp_path,
        batch_id=batch_id,
        task="cap",
        samples=[("img-a", "diag")],
    )
    import_dir = ls_import_task_dir(batch_id, TaskType.CAP, data_root=tmp_path)
    import_dir.mkdir(parents=True, exist_ok=True)
    sentinel = [{"id": "keep-me"}]
    tasks_path = import_dir / TASKS_JSON_NAME
    write_json(tasks_path, sentinel)

    export = tmp_path / "cap.json"
    write_json(
        export,
        [_cap_task(image_id="img-a", caption="x", rework="yes")],
    )
    rework_import_from_export(
        export,
        batch_id=batch_id,
        task="cap",
        data_root=tmp_path,
    )
    assert read_json(tasks_path) == sentinel
    assert (import_dir / REWORK_TASKS_JSON_NAME).is_file()
