"""M12.4 gate: SEG/DET/CAP run independently without touching sibling trees."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import BBox, DetAnnotation, TaskAnnotationResult, TaskType
from mma.common.paths import (
    ls_import_task_dir,
    results_current_dir,
    results_task_dir,
    task_package_dir,
)
from mma.converters.seg_brush import mask_to_ls_rle
from mma.exporters import export_split_from_export, overwrite_current
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.importers import TASKS_JSON_NAME, build_ls_import_tasks

_BATCH = "batch1"
_TASKS = ("cap", "det", "seg")


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _others(task: str) -> tuple[str, ...]:
    return tuple(name for name in _TASKS if name != task)


def _write_jpg(path: Path, *, size: tuple[int, int] = (8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 80, 40)).save(path, format="JPEG")


def _seed_package(
    data_root: Path,
    task: str,
    image_id: str,
    *,
    size: tuple[int, int] = (8, 6),
) -> None:
    package_dir = task_package_dir(_BATCH, task, data_root=data_root)
    _write_jpg(package_dir / "images" / f"{image_id}.jpg", size=size)
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{_BATCH}__{task}",
            "task_type": task.upper(),
            "batch_id": _BATCH,
            "samples": [
                {
                    "image_id": image_id,
                    "image_path": f"images/{image_id}.jpg",
                    "diagnosis_text": f"diag-{image_id}",
                }
            ],
        },
    )


def _assert_only_task_subdir(parent: Path, task: str) -> None:
    assert parent.is_dir()
    assert {child.name for child in parent.iterdir()} == {task}


def _assert_sibling_packages_and_ls_import_absent(
    data_root: Path, task: str
) -> None:
    for other in _others(task):
        assert not task_package_dir(_BATCH, other, data_root=data_root).exists()
        assert not ls_import_task_dir(_BATCH, other, data_root=data_root).exists()


def _assert_sibling_results_absent(data_root: Path, task: str) -> None:
    for other in _others(task):
        assert not results_task_dir(_BATCH, other, data_root=data_root).exists()


def _run_ls_import_only_this_task(tmp_path: Path, task: str) -> None:
    image_id = f"img-{task}"
    size = (100, 50) if task == "det" else (8, 6)
    _seed_package(tmp_path, task, image_id, size=size)

    out = build_ls_import_tasks(_BATCH, task, data_root=tmp_path)
    assert out == (
        ls_import_task_dir(_BATCH, task, data_root=tmp_path) / TASKS_JSON_NAME
    )
    tasks = read_json(out)
    assert len(tasks) == 1
    assert tasks[0]["data"]["image_id"] == image_id

    _assert_only_task_subdir(tmp_path / "task_packages" / _BATCH, task)
    _assert_only_task_subdir(tmp_path / "ls_import" / _BATCH, task)
    _assert_sibling_packages_and_ls_import_absent(tmp_path, task)


def _export_payload_cap(image_id: str) -> dict:
    return {
        "data": {
            "image_id": image_id,
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
                        "value": {"text": ["ok"]},
                    },
                    _choice("human_confirmed", "yes"),
                    _choice("needs_rework", "no"),
                ],
            }
        ],
    }


def _export_payload_det(image_id: str) -> dict:
    return {
        "data": {
            "image_id": image_id,
            "package_id": f"{_BATCH}__det",
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


def _export_payload_seg(image_id: str) -> dict:
    rle = mask_to_ls_rle([[1, 0], [0, 1]])
    return {
        "data": {
            "image_id": image_id,
            "package_id": f"{_BATCH}__seg",
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


def _run_export_split_only_this_task(
    tmp_path: Path, task: str, payload: dict, image_id: str
) -> None:
    if task == "det":
        images = tmp_path / "task_packages" / _BATCH / "det" / "images"
        images.mkdir(parents=True)
        Image.new("RGB", (200, 100), color=(1, 2, 3)).save(
            images / f"{image_id}.jpg"
        )
    write_json(
        task_package_dir(_BATCH, task, data_root=tmp_path) / "manifest.json",
        {
            "package_id": f"{_BATCH}__{task}",
            "task_type": task.upper(),
            "batch_id": _BATCH,
            "samples": [
                {
                    "image_id": image_id,
                    "image_path": f"images/{image_id}.jpg",
                    "diagnosis_text": f"diag-{image_id}",
                }
            ],
        },
    )
    export = tmp_path / f"{task}.json"
    write_json(export, [payload])
    export_split_from_export(
        export,
        batch_id=_BATCH,
        task=task,
        data_root=tmp_path,
    )
    assert results_task_dir(_BATCH, task, data_root=tmp_path).is_dir()
    _assert_only_task_subdir(tmp_path / "results" / _BATCH, task)
    _assert_sibling_results_absent(tmp_path, task)


def test_m12_4_ls_import_cap_without_other_task_packages(tmp_path: Path) -> None:
    _run_ls_import_only_this_task(tmp_path, "cap")


def test_m12_4_ls_import_det_without_other_task_packages(tmp_path: Path) -> None:
    _run_ls_import_only_this_task(tmp_path, "det")


def test_m12_4_ls_import_seg_without_other_task_packages(tmp_path: Path) -> None:
    _run_ls_import_only_this_task(tmp_path, "seg")


def test_m12_4_export_split_cap_writes_only_cap_results(tmp_path: Path) -> None:
    image_id = "img-cap-iso"
    _run_export_split_only_this_task(
        tmp_path, "cap", _export_payload_cap(image_id), image_id
    )


def test_m12_4_export_split_det_writes_only_det_results(tmp_path: Path) -> None:
    image_id = "img-det-iso"
    _run_export_split_only_this_task(
        tmp_path, "det", _export_payload_det(image_id), image_id
    )


def test_m12_4_export_split_seg_writes_only_seg_results(tmp_path: Path) -> None:
    image_id = "img-seg-iso"
    _run_export_split_only_this_task(
        tmp_path, "seg", _export_payload_seg(image_id), image_id
    )


def test_m12_4_export_split_cap_does_not_rewrite_det_current(
    tmp_path: Path,
) -> None:
    det_item = TaskAnnotationResult(
        image_id="img-det-mark",
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
        human_confirmed=True,
        needs_rework=False,
    )
    overwrite_current(
        [det_item],
        batch_id=_BATCH,
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    det_path = (
        results_current_dir(_BATCH, TaskType.DET, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    )
    before = det_path.read_bytes()

    image_id = "img-cap-iso"
    write_json(
        task_package_dir(_BATCH, "cap", data_root=tmp_path) / "manifest.json",
        {
            "package_id": f"{_BATCH}__cap",
            "task_type": "CAP",
            "batch_id": _BATCH,
            "samples": [
                {
                    "image_id": image_id,
                    "image_path": f"images/{image_id}.jpg",
                    "diagnosis_text": f"diag-{image_id}",
                }
            ],
        },
    )
    write_json(tmp_path / "cap.json", [_export_payload_cap(image_id)])
    export_split_from_export(
        tmp_path / "cap.json",
        batch_id=_BATCH,
        task=TaskType.CAP,
        data_root=tmp_path,
    )

    assert det_path.read_bytes() == before
    assert not results_task_dir(
        _BATCH, TaskType.SEG, data_root=tmp_path
    ).exists()
    results_root = tmp_path / "results" / _BATCH
    assert {child.name for child in results_root.iterdir()} == {"cap", "det"}
