"""M12.5 gate: CAP rework loop via previous_annotations → merge self-contained final."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import (
    BBox,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.converters.seg_brush import save_binary_mask_png
from mma.exporters import export_split_from_export, overwrite_current
from mma.exporters.previous_annotations import previous_annotations_json_path
from mma.importers import REWORK_TASKS_JSON_NAME, rework_import_from_export
from mma.merge import final_image_path, final_seg_mask_ref, merge_to_final

_BATCH = "batch1"
_IMAGE_ID = "img-loop"
_FIXED_CAPTION = "fixed-by-human"


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _cap_export_task(*, caption: str) -> dict:
    return {
        "data": {
            "image_id": _IMAGE_ID,
            "package_id": f"{_BATCH}__cap",
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
                        "value": {"text": [caption]},
                    },
                    _choice("human_confirmed", "yes"),
                    _choice("needs_rework", "no"),
                ],
            }
        ],
    }


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


def _seed_ready_det_seg(data_root: Path) -> None:
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
    _write_manual_mask(data_root)


def _seed_cap_package(data_root: Path) -> None:
    package_dir = data_root / "task_packages" / _BATCH / "cap"
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 6), color=(10, 20, 30)).save(
        images_dir / f"{_IMAGE_ID}.jpg"
    )
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{_BATCH}__cap",
            "task_type": "CAP",
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


def _round1_empty_cap(data_root: Path) -> tuple[Path, Path]:
    export = data_root / "cap_round1.json"
    write_json(export, [_cap_export_task(caption="")])
    return export_split_from_export(
        export,
        batch_id=_BATCH,
        task=TaskType.CAP,
        data_root=data_root,
    )


def _prepare_cap_in_rework(data_root: Path) -> None:
    _write_processed(data_root)
    _seed_ready_det_seg(data_root)
    _seed_cap_package(data_root)
    normal_path, rework_path = _round1_empty_cap(data_root)
    assert read_json(normal_path) == []
    rework = read_json(rework_path)
    assert [item["image_id"] for item in rework] == [_IMAGE_ID]
    assert previous_annotations_json_path(
        _BATCH, TaskType.CAP, data_root=data_root
    ).is_file()
    assert not (data_root / "prelabels").exists()


def test_m12_5_merge_blocked_while_cap_in_rework(tmp_path: Path) -> None:
    _prepare_cap_in_rework(tmp_path)
    with pytest.raises(ValueError):
        merge_to_final(_BATCH, data_root=tmp_path)
    assert not (tmp_path / "final").exists()
    assert not (tmp_path / "prelabels").exists()


def test_m12_5_rework_import_then_fix_then_merge_self_contained(
    tmp_path: Path,
) -> None:
    _prepare_cap_in_rework(tmp_path)

    out = rework_import_from_export(
        None,
        batch_id=_BATCH,
        task=TaskType.CAP,
        data_root=tmp_path,
    )
    assert out.name == REWORK_TASKS_JSON_NAME
    tasks = read_json(out)
    assert len(tasks) == 1
    assert tasks[0]["data"]["image_id"] == _IMAGE_ID

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

    manifest = merge_to_final(_BATCH, data_root=tmp_path)
    final_dir = manifest.parent
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["cap"]["caption"] == _FIXED_CAPTION
    assert item["image_path"] == final_image_path(_IMAGE_ID)
    assert item["seg"]["mask_ref"] == final_seg_mask_ref(_IMAGE_ID)
    assert (final_dir / item["image_path"]).is_file()
    assert (final_dir / item["seg"]["mask_ref"]).is_file()
    assert not (tmp_path / "prelabels").exists()
