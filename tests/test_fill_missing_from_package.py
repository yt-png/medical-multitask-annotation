"""R1: task-package samples missing from an LS export become empty rework."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import (
    CapAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import results_manual_masks_dir
from mma.exporters import export_split_from_export, overwrite_current
from mma.exporters.apply_current_from_export import apply_current_from_export
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.exporters.fill_missing_from_package import fill_missing_from_package
from mma.importers import REWORK_TASKS_JSON_NAME, rework_import_from_export


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _write_package_manifest(
    data_root: Path,
    task: str,
    image_ids: list[str],
    *,
    batch_id: str = "batch1",
) -> None:
    write_json(
        data_root / "task_packages" / batch_id / task / "manifest.json",
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
                for image_id in image_ids
            ],
        },
    )


def _write_package_jpg(
    data_root: Path,
    task: str,
    image_id: str,
    *,
    batch_id: str = "batch1",
    size: tuple[int, int] = (8, 6),
) -> None:
    images = data_root / "task_packages" / batch_id / task / "images"
    images.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(10, 20, 30)).save(images / f"{image_id}.jpg")


def _cap_export_task(
    image_id: str,
    *,
    caption: str,
    rework: str = "no",
    human: str = "yes",
) -> dict:
    return {
        "data": {
            "image_id": image_id,
            "package_id": "batch1__cap",
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
                    _choice("human_confirmed", human),
                    _choice("needs_rework", rework),
                ],
            }
        ],
    }


def test_fill_missing_appends_unconfirmed_empty_cap(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-a", "img-b", "img-c"])
    parsed = (
        TaskAnnotationResult(
            image_id="img-a",
            task_type=TaskType.CAP,
            annotation=CapAnnotation(caption="kept"),
            human_confirmed=True,
            needs_rework=False,
            package_id="batch1__cap",
        ),
    )
    filled = fill_missing_from_package(
        parsed,
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
        export_round=2,
    )
    assert [item.image_id for item in filled] == ["img-a", "img-b", "img-c"]
    assert filled[0].annotation.caption == "kept"
    for item in filled[1:]:
        assert item.human_confirmed is False
        assert item.needs_rework is False
        assert item.annotation.caption == ""
        assert item.package_id == "batch1__cap"
        assert item.export_round == 2


def test_fill_missing_skips_ids_already_in_current(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-a", "img-b"])
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-b",
                task_type=TaskType.CAP,
                annotation=CapAnnotation(caption="keep-b"),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    filled = fill_missing_from_package(
        (),
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert [item.image_id for item in filled] == ["img-a"]
    assert filled[0].human_confirmed is False
    assert filled[0].annotation.caption == ""


def test_fill_missing_rejects_export_ids_not_in_package(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-a"])
    parsed = (
        TaskAnnotationResult(
            image_id="img-extra",
            task_type=TaskType.CAP,
            annotation=CapAnnotation(caption="x"),
            human_confirmed=True,
            needs_rework=False,
        ),
    )
    with pytest.raises(ValueError, match="not in task package"):
        fill_missing_from_package(
            parsed,
            batch_id="batch1",
            task_type=TaskType.CAP,
            data_root=tmp_path,
        )


def test_fill_missing_requires_package_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="task package manifest not found"):
        fill_missing_from_package(
            (),
            batch_id="batch1",
            task_type=TaskType.CAP,
            data_root=tmp_path,
        )


def test_export_split_missing_package_sample_goes_rework(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-ok", "img-miss"])
    export = tmp_path / "cap.json"
    write_json(export, [_cap_export_task("img-ok", caption="ok")])
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.CAP,
        data_root=tmp_path,
    )
    normal = read_json(normal_path)
    rework = read_json(rework_path)
    assert [item["image_id"] for item in normal] == ["img-ok"]
    assert [item["image_id"] for item in rework] == ["img-miss"]
    assert rework[0]["human_confirmed"] is False
    assert rework[0]["needs_rework"] is False
    assert rework[0]["annotation"]["caption"] == ""
    current = read_json(
        tmp_path / "results" / "batch1" / "cap" / "current" / ANNOTATIONS_JSON_NAME
    )
    assert [item["image_id"] for item in current] == ["img-ok", "img-miss"]


def test_export_split_second_round_subset_preserves_normal(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-ok", "img-fix", "img-miss"])
    round1 = tmp_path / "round1.json"
    write_json(
        round1,
        [
            _cap_export_task("img-ok", caption="ok"),
            _cap_export_task("img-fix", caption="bad", rework="yes"),
        ],
    )
    export_split_from_export(
        round1, batch_id="batch1", task=TaskType.CAP, data_root=tmp_path
    )
    round2 = tmp_path / "round2.json"
    write_json(round2, [_cap_export_task("img-fix", caption="fixed")])
    normal_path, rework_path = export_split_from_export(
        round2, batch_id="batch1", task=TaskType.CAP, data_root=tmp_path
    )
    normal = read_json(normal_path)
    rework = read_json(rework_path)
    by_normal = {item["image_id"]: item for item in normal}
    assert set(by_normal) == {"img-ok", "img-fix"}
    assert by_normal["img-ok"]["annotation"]["caption"] == "ok"
    assert by_normal["img-fix"]["annotation"]["caption"] == "fixed"
    assert [item["image_id"] for item in rework] == ["img-miss"]


def test_empty_export_with_package_and_no_current_fills_all_rework(
    tmp_path: Path,
) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-a", "img-b"])
    empty = tmp_path / "empty.json"
    write_json(empty, [])
    normal_path, rework_path = export_split_from_export(
        empty, batch_id="batch1", task=TaskType.CAP, data_root=tmp_path
    )
    assert read_json(normal_path) == []
    rework = read_json(rework_path)
    assert [item["image_id"] for item in rework] == ["img-a", "img-b"]
    assert all(item["human_confirmed"] is False for item in rework)


def test_apply_current_without_package_manifest_fails(tmp_path: Path) -> None:
    export = tmp_path / "cap.json"
    write_json(export, [_cap_export_task("img-a", caption="x")])
    with pytest.raises(ValueError, match="task package manifest not found"):
        apply_current_from_export(
            export, batch_id="batch1", task="cap", data_root=tmp_path
        )


def test_apply_current_rejects_export_id_outside_package(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-a"])
    export = tmp_path / "cap.json"
    write_json(
        export,
        [
            _cap_export_task("img-a", caption="ok"),
            _cap_export_task("img-extra", caption="nope"),
        ],
    )
    with pytest.raises(ValueError, match="not in task package"):
        apply_current_from_export(
            export, batch_id="batch1", task="cap", data_root=tmp_path
        )


def test_export_split_missing_det_sample_goes_rework(tmp_path: Path) -> None:
    _write_package_jpg(tmp_path, "det", "img-ok", size=(200, 100))
    _write_package_manifest(tmp_path, "det", ["img-ok", "img-miss"])
    export = tmp_path / "det.json"
    write_json(
        export,
        [
            {
                "data": {
                    "image_id": "img-ok",
                    "package_id": "batch1__det",
                    "diagnosis_text": "diag",
                },
                "annotations": [
                    {
                        "id": 1,
                        "was_cancelled": False,
                        "updated_at": "2026-08-11T00:00:00.000000Z",
                        "result": [
                            {
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
                            },
                            _choice("human_confirmed", "yes"),
                            _choice("needs_rework", "no"),
                        ],
                    }
                ],
            }
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export, batch_id="batch1", task=TaskType.DET, data_root=tmp_path
    )
    assert [item["image_id"] for item in read_json(normal_path)] == ["img-ok"]
    rework = read_json(rework_path)
    assert [item["image_id"] for item in rework] == ["img-miss"]
    assert rework[0]["annotation"]["bboxes"] == []
    assert rework[0]["human_confirmed"] is False


def test_export_split_missing_seg_writes_empty_mask_and_rework_import(
    tmp_path: Path,
) -> None:
    from mma.converters.seg_brush import mask_to_ls_rle, manual_mask_ref

    _write_package_jpg(tmp_path, "seg", "img-ok", size=(2, 2))
    _write_package_jpg(tmp_path, "seg", "img-miss", size=(4, 3))
    _write_package_manifest(tmp_path, "seg", ["img-ok", "img-miss"])
    rle = mask_to_ls_rle([[1, 0], [0, 1]])
    export = tmp_path / "seg.json"
    write_json(
        export,
        [
            {
                "data": {
                    "image_id": "img-ok",
                    "package_id": "batch1__seg",
                    "diagnosis_text": "diag",
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
                                    "rle": rle,
                                    "brushlabels": ["lesion"],
                                },
                            },
                            _choice("human_confirmed", "yes"),
                            _choice("needs_rework", "no"),
                        ],
                    }
                ],
            }
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export, batch_id="batch1", task=TaskType.SEG, data_root=tmp_path
    )
    assert [item["image_id"] for item in read_json(normal_path)] == ["img-ok"]
    rework = read_json(rework_path)
    assert [item["image_id"] for item in rework] == ["img-miss"]
    assert rework[0]["annotation"]["mask_ref"] == manual_mask_ref("img-miss")
    assert rework[0]["annotation"]["has_foreground"] is False
    mask_path = (
        results_manual_masks_dir("batch1", data_root=tmp_path) / "img-miss_manual.png"
    )
    assert mask_path.is_file()

    out = rework_import_from_export(
        None, batch_id="batch1", task=TaskType.SEG, data_root=tmp_path
    )
    assert out.name == REWORK_TASKS_JSON_NAME
    tasks = read_json(out)
    assert len(tasks) == 1
    assert tasks[0]["data"]["image_id"] == "img-miss"
