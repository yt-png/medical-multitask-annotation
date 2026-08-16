"""Tests for Label Studio import task builder (V1 empty first-round tasks)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from mma.cli import main
from mma.common.io import write_json
from mma.common.models import TaskType
from mma.common.paths import ls_import_task_dir, task_package_dir
from mma.importers import (
    LOCAL_FILES_PREFIX,
    TASKS_JSON_NAME,
    build_ls_import_tasks,
    to_local_files_url,
)
from mma.importers.validate_prelabel_coverage import validate_prelabel_coverage

_ALLOWED_DATA_KEYS = frozenset(
    {"image", "image_id", "package_id", "diagnosis_text"}
)


def _write_jpg(path: Path, *, size: tuple[int, int] = (8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 80, 40)).save(path, format="JPEG")


def _write_package_manifest(
    data_root: Path,
    batch_id: str,
    task: str,
    image_ids: list[str],
) -> Path:
    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    package_dir.mkdir(parents=True, exist_ok=True)
    task_type = {"seg": "SEG", "det": "DET", "cap": "CAP"}[task]
    payload = {
        "package_id": f"{batch_id}__{task}",
        "task_type": task_type,
        "batch_id": batch_id,
        "samples": [
            {
                "image_id": image_id,
                "image_path": f"images/{image_id}.jpg",
                "diagnosis_text": f"diag-{image_id}",
            }
            for image_id in image_ids
        ],
    }
    path = package_dir / "manifest.json"
    write_json(path, payload)
    return path


def _seed_package_image(
    data_root: Path,
    batch_id: str,
    task: str,
    image_id: str,
    *,
    size: tuple[int, int] = (8, 6),
) -> Path:
    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    image_path = package_dir / "images" / f"{image_id}.jpg"
    _write_jpg(image_path, size=size)
    return image_path


def _seed_package(
    data_root: Path,
    batch_id: str,
    task: str,
    image_ids: list[str],
    *,
    size: tuple[int, int] = (8, 6),
) -> None:
    for image_id in image_ids:
        _seed_package_image(data_root, batch_id, task, image_id, size=size)
    _write_package_manifest(data_root, batch_id, task, image_ids)


def _assert_empty_first_round_task(task: dict, *, image_id: str, package_id: str) -> None:
    assert "predictions" not in task
    assert set(task.keys()) == {"data"}
    data = task["data"]
    assert set(data.keys()) == _ALLOWED_DATA_KEYS
    assert data["image_id"] == image_id
    assert data["package_id"] == package_id
    assert data["diagnosis_text"] == f"diag-{image_id}"
    assert data["image"].startswith(LOCAL_FILES_PREFIX)
    assert "mask_ref" not in data


def test_to_local_files_url() -> None:
    assert (
        to_local_files_url("task_packages/b/seg/images/a.jpg")
        == f"{LOCAL_FILES_PREFIX}task_packages/b/seg/images/a.jpg"
    )


def test_validate_prelabel_coverage_still_available_as_legacy_helper() -> None:
    """M4.2: helper file kept; no longer used by first-round import."""

    validate_prelabel_coverage(["a", "b", "c"], ["a", "b", "c"])
    with pytest.raises(ValueError, match="Missing prelabels"):
        validate_prelabel_coverage(["a", "b", "c"], ["a", "b"])
    with pytest.raises(ValueError, match="Unknown prelabels"):
        validate_prelabel_coverage(["a", "b"], ["a", "b", "c"])
    validate_prelabel_coverage(["a", "b", "c"], ["c", "a", "b"])


def test_build_without_prelabels_writes_empty_cap_tasks(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])
    assert not (data_root / "prelabels").exists()

    out = build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    assert out.name == TASKS_JSON_NAME
    assert out.is_file()

    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert len(tasks) == 1
    _assert_empty_first_round_task(
        tasks[0],
        image_id=image_id,
        package_id=f"{batch_id}__cap",
    )
    assert "task_packages/demo_batch/cap/images/" in tasks[0]["data"]["image"]


def test_build_det_empty_tasks_no_rectangle_predictions(tmp_path: Path) -> None:
    """V1 rewrite of former DET prediction assertion."""

    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "det", [image_id], size=(100, 50))

    out = build_ls_import_tasks(batch_id, TaskType.DET, data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    _assert_empty_first_round_task(
        tasks[0],
        image_id=image_id,
        package_id=f"{batch_id}__det",
    )


def test_build_seg_empty_tasks_no_mask_ref_or_polygon(tmp_path: Path) -> None:
    """V1 rewrite of former SEG polygon / mask_ref assertion."""

    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "seg", [image_id], size=(4, 4))

    out = build_ls_import_tasks(batch_id, "seg", data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    _assert_empty_first_round_task(
        tasks[0],
        image_id=image_id,
        package_id=f"{batch_id}__seg",
    )


def test_ls_import_ignores_orphan_prelabels_directory(tmp_path: Path) -> None:
    """Former coverage mismatch cases: prelabels no longer gate import."""

    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    package_ids = ["a", "b", "c"]
    _seed_package(data_root, batch_id, "cap", package_ids)
    # Orphan prelabels tree (subset / supersets) must not affect empty import.
    pre_dir = data_root / "prelabels" / batch_id / "cap"
    pre_dir.mkdir(parents=True)
    (pre_dir / "prelabels.json").write_text("{}", encoding="utf-8")

    out = build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert {t["data"]["image_id"] for t in tasks} == set(package_ids)
    assert all("predictions" not in t for t in tasks)


def test_sample_order_follows_package_manifest(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    ordered = ["c", "a", "b"]
    _seed_package(data_root, batch_id, "cap", ordered)

    out = build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert [t["data"]["image_id"] for t in tasks] == ordered


def test_missing_package_manifest_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    with pytest.raises(ValueError, match="task package manifest not found"):
        build_ls_import_tasks("demo_batch", "cap", data_root=data_root)


def test_missing_image_raises_with_image_id(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _write_package_manifest(data_root, batch_id, "cap", [image_id])
    with pytest.raises(ValueError, match="demo_batch__000001"):
        build_ls_import_tasks(batch_id, "cap", data_root=data_root)


def test_local_root_override_changes_relative_segment(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace" / "data"
    local_root = tmp_path / "workspace"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])

    out = build_ls_import_tasks(
        batch_id,
        "cap",
        data_root=data_root,
        local_root=local_root,
    )
    tasks = json.loads(out.read_text(encoding="utf-8"))
    image_url = tasks[0]["data"]["image"]
    assert image_url.startswith(LOCAL_FILES_PREFIX)
    assert image_url.endswith(
        f"data/task_packages/{batch_id}/cap/images/{image_id}.jpg"
    )


def test_does_not_copy_images_into_ls_import(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])
    build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    import_dir = ls_import_task_dir(batch_id, "cap", data_root=data_root)
    names = sorted(p.name for p in import_dir.iterdir())
    assert names == [TASKS_JSON_NAME]


def test_ls_import_cli_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])
    code = main(
        [
            "ls-import",
            "--batch",
            batch_id,
            "--task",
            "cap",
            "--data-root",
            str(data_root),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith(TASKS_JSON_NAME)
    assert Path(out).is_file()
    tasks = json.loads(Path(out).read_text(encoding="utf-8"))
    assert "predictions" not in tasks[0]


def test_ls_import_cli_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "ls-import",
            "--batch",
            "demo_batch",
            "--task",
            "cap",
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    assert code == 2
    assert "ls-import" in capsys.readouterr().err
