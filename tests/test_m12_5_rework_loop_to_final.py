"""M12.5 gate: CAP/DET/SEG rework loop via previous_annotations → merge."""

from __future__ import annotations

import json
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
from mma.converters.seg_brush import mask_to_ls_rle, save_binary_mask_png
from mma.exporters import export_split_from_export, overwrite_current
from mma.exporters.previous_annotations import previous_annotations_json_path
from mma.importers import REWORK_TASKS_JSON_NAME, rework_import_from_export
from mma.merge import final_image_path, final_seg_mask_ref, merge_to_final

_BATCH = "batch1"
_IMAGE_ID = "img-loop"
_FIXED_CAPTION = "fixed-by-human"
_ANN_TS = "2026-08-11T00:00:00.000000Z"


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _confirmed_result(entries: list[dict]) -> list[dict]:
    return [
        {
            "id": 1,
            "was_cancelled": False,
            "updated_at": _ANN_TS,
            "result": [
                *entries,
                _choice("human_confirmed", "yes"),
                _choice("needs_rework", "no"),
            ],
        }
    ]


def _export_task(*, task: str, result_entries: list[dict]) -> dict:
    return {
        "data": {
            "image_id": _IMAGE_ID,
            "package_id": f"{_BATCH}__{task}",
            "diagnosis_text": "diag",
        },
        "annotations": _confirmed_result(result_entries),
    }


def _cap_export_task(*, caption: str) -> dict:
    return _export_task(
        task="cap",
        result_entries=[
            {
                "from_name": "cap_text",
                "to_name": "image",
                "type": "textarea",
                "value": {"text": [caption]},
            }
        ],
    )


def _det_export_task(*, boxes: list[dict] | None) -> dict:
    entries: list[dict] = []
    if boxes:
        entries.extend(boxes)
    return _export_task(task="det", result_entries=entries)


def _det_box_percent() -> dict:
    return {
        "from_name": "det_bbox",
        "to_name": "image",
        "type": "rectanglelabels",
        "value": {
            "x": 10.0,
            "y": 20.0,
            "width": 25.0,
            "height": 50.0,
            "rectanglelabels": ["object"],
        },
    }


def _seg_export_task(*, rle: list[int]) -> dict:
    labels = ["lesion"] if rle else []
    return _export_task(
        task="seg",
        result_entries=[
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "original_width": 2,
                "original_height": 2,
                "value": {
                    "format": "rle",
                    "rle": rle,
                    "brushlabels": labels,
                },
            }
        ],
    )


def _write_manual_mask(data_root: Path) -> None:
    path = (
        data_root
        / "results"
        / _BATCH
        / "seg"
        / "manual_masks"
        / f"{_IMAGE_ID}_manual.png"
    )
    save_binary_mask_png(path, [[1, 0], [0, 1]])


def _write_processed(data_root: Path) -> None:
    images_dir = data_root / "raw" / _BATCH / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_file = images_dir / f"{_IMAGE_ID}.jpg"
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(image_file)
    write_json(
        data_root / "processed" / _BATCH / "manifest.json",
        {
            "batch_id": _BATCH,
            "items": [
                {
                    "image_id": _IMAGE_ID,
                    "image_path": str(image_file.resolve()),
                    "diagnosis_text": f"diag-{_IMAGE_ID}",
                    "source_image_name": image_file.name,
                }
            ],
        },
    )


def _seed_task_package(
    data_root: Path,
    task: str,
    *,
    width: int,
    height: int,
) -> None:
    package_dir = data_root / "task_packages" / _BATCH / task
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), color=(10, 20, 30)).save(
        images_dir / f"{_IMAGE_ID}.jpg"
    )
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{_BATCH}__{task}",
            "task_type": task.upper(),
            "batch_id": _BATCH,
            "samples": [
                {
                    "image_id": _IMAGE_ID,
                    "image_path": f"images/{_IMAGE_ID}.jpg",
                    "diagnosis_text": "diag",
                }
            ],
        },
    )


def _seed_cap_package(data_root: Path) -> None:
    _seed_task_package(data_root, "cap", width=8, height=6)


def _seed_det_package(data_root: Path) -> None:
    _seed_task_package(data_root, "det", width=200, height=100)


def _seed_seg_package(data_root: Path) -> None:
    _seed_task_package(data_root, "seg", width=8, height=6)


def _seed_ready_cap(data_root: Path) -> None:
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id=_IMAGE_ID,
                task_type=TaskType.CAP,
                annotation=CapAnnotation(caption="ready-cap"),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id=_BATCH,
        task_type=TaskType.CAP,
        data_root=data_root,
    )


def _seed_ready_seg(data_root: Path) -> None:
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id=_IMAGE_ID,
                task_type=TaskType.SEG,
                annotation=SegAnnotation(
                    mask_ref=f"manual_masks/{_IMAGE_ID}_manual.png"
                ),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id=_BATCH,
        task_type=TaskType.SEG,
        data_root=data_root,
    )
    _write_manual_mask(data_root)


def _seed_ready_det(data_root: Path) -> None:
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id=_IMAGE_ID,
                task_type=TaskType.DET,
                annotation=DetAnnotation(
                    bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
                ),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id=_BATCH,
        task_type=TaskType.DET,
        data_root=data_root,
    )


def _seed_ready_det_seg(data_root: Path) -> None:
    _seed_ready_seg(data_root)
    _seed_ready_det(data_root)


def _round1_empty_cap(data_root: Path) -> tuple[Path, Path]:
    export = data_root / "cap_round1.json"
    write_json(export, [_cap_export_task(caption="")])
    return export_split_from_export(
        export,
        batch_id=_BATCH,
        task=TaskType.CAP,
        data_root=data_root,
    )


def _round1_empty_det(data_root: Path) -> tuple[Path, Path]:
    export = data_root / "det_round1.json"
    write_json(export, [_det_export_task(boxes=None)])
    return export_split_from_export(
        export,
        batch_id=_BATCH,
        task=TaskType.DET,
        data_root=data_root,
    )


def _round1_empty_seg(data_root: Path) -> tuple[Path, Path]:
    export = data_root / "seg_round1.json"
    write_json(export, [_seg_export_task(rle=[])])
    return export_split_from_export(
        export,
        batch_id=_BATCH,
        task=TaskType.SEG,
        data_root=data_root,
    )


def _assert_only_image_in_rework(
    data_root: Path,
    task_type: TaskType,
    normal_path: Path,
    rework_path: Path,
) -> None:
    assert read_json(normal_path) == []
    rework = read_json(rework_path)
    assert [item["image_id"] for item in rework] == [_IMAGE_ID]
    assert previous_annotations_json_path(
        _BATCH, task_type, data_root=data_root
    ).is_file()
    assert not (data_root / "prelabels").exists()


def _prepare_cap_in_rework(data_root: Path) -> None:
    _write_processed(data_root)
    _seed_ready_det_seg(data_root)
    _seed_cap_package(data_root)
    normal_path, rework_path = _round1_empty_cap(data_root)
    _assert_only_image_in_rework(
        data_root, TaskType.CAP, normal_path, rework_path
    )


def _prepare_det_in_rework(data_root: Path) -> None:
    _write_processed(data_root)
    _seed_ready_cap(data_root)
    _seed_ready_seg(data_root)
    _seed_det_package(data_root)
    normal_path, rework_path = _round1_empty_det(data_root)
    _assert_only_image_in_rework(
        data_root, TaskType.DET, normal_path, rework_path
    )


def _prepare_seg_in_rework(data_root: Path) -> None:
    _write_processed(data_root)
    _seed_ready_cap(data_root)
    _seed_ready_det(data_root)
    _seed_seg_package(data_root)
    normal_path, rework_path = _round1_empty_seg(data_root)
    _assert_only_image_in_rework(
        data_root, TaskType.SEG, normal_path, rework_path
    )


def _rework_import_one(data_root: Path, task_type: TaskType) -> list:
    out = rework_import_from_export(
        None,
        batch_id=_BATCH,
        task=task_type,
        data_root=data_root,
    )
    assert out.name == REWORK_TASKS_JSON_NAME
    tasks = read_json(out)
    assert len(tasks) == 1
    assert tasks[0]["data"]["image_id"] == _IMAGE_ID
    return tasks


def _assert_merge_self_contained(data_root: Path) -> dict:
    manifest = merge_to_final(_BATCH, data_root=data_root)
    final_dir = manifest.parent
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["image_path"] == final_image_path(_IMAGE_ID)
    assert item["seg"]["mask_ref"] == final_seg_mask_ref(_IMAGE_ID)
    assert (final_dir / item["image_path"]).is_file()
    assert (final_dir / item["seg"]["mask_ref"]).is_file()
    assert not (data_root / "prelabels").exists()
    return item


def test_m12_5_merge_blocked_while_cap_in_rework(tmp_path: Path) -> None:
    _prepare_cap_in_rework(tmp_path)
    with pytest.raises(ValueError):
        merge_to_final(_BATCH, data_root=tmp_path)
    assert not (tmp_path / "final").exists()
    assert not (tmp_path / "prelabels").exists()


def test_m12_5_merge_blocked_while_det_in_rework(tmp_path: Path) -> None:
    _prepare_det_in_rework(tmp_path)
    with pytest.raises(ValueError):
        merge_to_final(_BATCH, data_root=tmp_path)
    assert not (tmp_path / "final").exists()
    assert not (tmp_path / "prelabels").exists()


def test_m12_5_merge_blocked_while_seg_in_rework(tmp_path: Path) -> None:
    _prepare_seg_in_rework(tmp_path)
    with pytest.raises(ValueError):
        merge_to_final(_BATCH, data_root=tmp_path)
    assert not (tmp_path / "final").exists()
    assert not (tmp_path / "prelabels").exists()


def test_m12_5_rework_import_then_fix_then_merge_self_contained(
    tmp_path: Path,
) -> None:
    _prepare_cap_in_rework(tmp_path)
    _rework_import_one(tmp_path, TaskType.CAP)

    round2 = tmp_path / "cap_round2.json"
    write_json(round2, [_cap_export_task(caption=_FIXED_CAPTION)])
    normal_path, rework_path = export_split_from_export(
        round2,
        batch_id=_BATCH,
        task=TaskType.CAP,
        data_root=tmp_path,
    )
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert len(normal) == 1
    assert normal[0]["annotation"]["caption"] == _FIXED_CAPTION

    item = _assert_merge_self_contained(tmp_path)
    assert item["cap"]["caption"] == _FIXED_CAPTION


def test_m12_5_det_rework_import_then_fix_then_merge(tmp_path: Path) -> None:
    _prepare_det_in_rework(tmp_path)
    _rework_import_one(tmp_path, TaskType.DET)

    round2 = tmp_path / "det_round2.json"
    write_json(round2, [_det_export_task(boxes=[_det_box_percent()])])
    normal_path, rework_path = export_split_from_export(
        round2,
        batch_id=_BATCH,
        task=TaskType.DET,
        data_root=tmp_path,
    )
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert len(normal) == 1
    assert len(normal[0]["annotation"]["bboxes"]) == 1

    item = _assert_merge_self_contained(tmp_path)
    assert len(item["det"]["bboxes"]) == 1
    # 200x100 package image: 10/20/25/50 percent → 20/20/50/50 pixels
    box = item["det"]["bboxes"][0]
    assert box["x"] == 20.0
    assert box["y"] == 20.0
    assert box["width"] == 50.0
    assert box["height"] == 50.0


def test_m12_5_seg_rework_import_then_fix_then_merge(tmp_path: Path) -> None:
    _prepare_seg_in_rework(tmp_path)
    _rework_import_one(tmp_path, TaskType.SEG)

    round2 = tmp_path / "seg_round2.json"
    write_json(
        round2, [_seg_export_task(rle=mask_to_ls_rle([[1, 0], [0, 1]]))]
    )
    normal_path, rework_path = export_split_from_export(
        round2,
        batch_id=_BATCH,
        task=TaskType.SEG,
        data_root=tmp_path,
    )
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert len(normal) == 1
    assert normal[0]["annotation"]["has_foreground"] is True

    item = _assert_merge_self_contained(tmp_path)
    # final SEG 契约仅 mask_ref（has_foreground 在 current/，不写入 final）
    assert item["seg"] == {"mask_ref": final_seg_mask_ref(_IMAGE_ID)}
