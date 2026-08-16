"""M12.3 gate: main path runs without prelabels/ or prediction files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.common.paths import task_package_dir
from mma.converters.seg_brush import mask_to_ls_rle
from mma.exporters import export_split_from_export
from mma.importers import LOCAL_FILES_PREFIX, build_ls_import_tasks

_ALLOWED_DATA_KEYS = frozenset(
    {"image", "image_id", "package_id", "diagnosis_text"}
)
_TASKS = ("cap", "det", "seg")


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _write_export(path: Path, tasks: list[dict]) -> Path:
    write_json(path, tasks)
    return path


def _write_jpg(path: Path, *, size: tuple[int, int] = (8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 80, 40)).save(path, format="JPEG")


def _seed_package(
    data_root: Path,
    batch_id: str,
    task: str,
    image_id: str,
    *,
    size: tuple[int, int] = (8, 6),
) -> None:
    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    _write_jpg(package_dir / "images" / f"{image_id}.jpg", size=size)
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
                    "diagnosis_text": f"diag-{image_id}",
                }
            ],
        },
    )


def _assert_no_prelabels(data_root: Path) -> None:
    assert not (data_root / "prelabels").exists()


def _assert_empty_first_round_task(
    task: dict, *, image_id: str, package_id: str
) -> None:
    assert "predictions" not in task
    assert set(task.keys()) == {"data"}
    data = task["data"]
    assert set(data.keys()) == _ALLOWED_DATA_KEYS
    assert data["image_id"] == image_id
    assert data["package_id"] == package_id
    assert data["diagnosis_text"] == f"diag-{image_id}"
    assert data["image"].startswith(LOCAL_FILES_PREFIX)
    assert "mask_ref" not in data


def _assert_only_in_normal(
    normal_path: Path,
    rework_path: Path,
    *,
    image_id: str,
) -> list[dict]:
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert len(normal) == 1
    assert normal[0]["image_id"] == image_id
    assert normal[0]["human_confirmed"] is True
    assert normal[0]["needs_rework"] is False
    return normal


def test_m12_3_ls_import_without_prelabels_for_cap_det_seg(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "batch1"
    for task in _TASKS:
        image_id = f"img-{task}"
        size = (100, 50) if task == "det" else (8, 6)
        _seed_package(data_root, batch_id, task, image_id, size=size)
    _assert_no_prelabels(data_root)

    for task in _TASKS:
        image_id = f"img-{task}"
        out = build_ls_import_tasks(batch_id, task, data_root=data_root)
        tasks = read_json(out)
        assert len(tasks) == 1
        _assert_empty_first_round_task(
            tasks[0],
            image_id=image_id,
            package_id=f"{batch_id}__{task}",
        )
    _assert_no_prelabels(data_root)


def test_m12_3_export_split_cap_without_predictions_key(tmp_path: Path) -> None:
    task = {
        "data": {
            "image_id": "img-cap-np",
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
                        "value": {"text": ["ok"]},
                    },
                    _choice("human_confirmed", "yes"),
                    _choice("needs_rework", "no"),
                ],
            }
        ],
    }
    assert "predictions" not in task
    export = _write_export(tmp_path / "cap.json", [task])
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.CAP,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-cap-np"
    )
    assert normal[0]["annotation"]["caption"] == "ok"


def test_m12_3_export_split_det_without_predictions_key(tmp_path: Path) -> None:
    images = tmp_path / "task_packages" / "batch1" / "det" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (200, 100), color=(1, 2, 3)).save(images / "img-det-np.jpg")
    task = {
        "data": {
            "image_id": "img-det-np",
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
    assert "predictions" not in task
    export = _write_export(tmp_path / "det.json", [task])
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.DET,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-det-np"
    )
    assert len(normal[0]["annotation"]["bboxes"]) == 1


def test_m12_3_export_split_seg_without_predictions_key(tmp_path: Path) -> None:
    rle = mask_to_ls_rle([[1, 0], [0, 1]])
    task = {
        "data": {
            "image_id": "img-seg-np",
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
    assert "predictions" not in task
    export = _write_export(tmp_path / "seg.json", [task])
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.SEG,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-seg-np"
    )
    assert normal[0]["annotation"]["has_foreground"] is True
