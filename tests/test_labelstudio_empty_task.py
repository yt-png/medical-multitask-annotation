"""M9.1: first-round LS tasks for SEG/DET/CAP without predictions or prelabels."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from mma.common.io import write_json
from mma.common.paths import task_package_dir
from mma.importers import build_ls_import_tasks

_ALLOWED_DATA_KEYS = frozenset(
    {"image", "image_id", "package_id", "diagnosis_text"}
)


def _write_jpg(path: Path, *, size: tuple[int, int] = (8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 80, 40)).save(path, format="JPEG")


def _seed_package(
    data_root: Path,
    batch_id: str,
    task: str,
    image_id: str,
) -> None:
    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    _write_jpg(package_dir / "images" / f"{image_id}.jpg")
    task_type = {"seg": "SEG", "det": "DET", "cap": "CAP"}[task]
    write_json(
        package_dir / "manifest.json",
        {
            "package_id": f"{batch_id}__{task}",
            "task_type": task_type,
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


def _assert_empty_task(task: dict) -> None:
    assert "predictions" not in task
    assert "prelabels" not in task
    assert set(task.keys()) == {"data"}
    data = task["data"]
    assert set(data.keys()) == _ALLOWED_DATA_KEYS
    assert "predictions" not in data
    assert "prelabels" not in data


def test_empty_ls_task_seg_det_cap_without_predictions_or_prelabels(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    batch_id = "m9_empty"
    assert not (data_root / "prelabels").exists()

    for task in ("seg", "det", "cap"):
        image_id = f"{batch_id}__{task}__000001"
        _seed_package(data_root, batch_id, task, image_id)
        out = build_ls_import_tasks(batch_id, task, data_root=data_root)
        tasks = json.loads(out.read_text(encoding="utf-8"))
        assert len(tasks) == 1
        _assert_empty_task(tasks[0])
        assert tasks[0]["data"]["image_id"] == image_id

    assert not (data_root / "prelabels").exists()
