"""Tests for Label Studio import task builder (T3.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from mma.cli import main
from mma.common.io import write_json
from mma.common.models import TaskType
from mma.common.paths import ls_import_task_dir, prelabels_task_dir, task_package_dir
from mma.formats import SCHEMA_VERSION
from mma.importers import (
    LOCAL_FILES_PREFIX,
    TASKS_JSON_NAME,
    build_ls_import_tasks,
    to_local_files_url,
    validate_prelabel_coverage,
)


def _write_jpg(path: Path, *, size: tuple[int, int] = (8, 6)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 80, 40)).save(path, format="JPEG")


def _write_mask(path: Path, pixels: list[list[int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    height = len(pixels)
    width = len(pixels[0])
    img = Image.new("L", (width, height))
    img.putdata([255 if cell else 0 for row in pixels for cell in row])
    img.save(path)


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


def _write_prelabels(
    data_root: Path,
    batch_id: str,
    task: str,
    *,
    items: list[tuple[str, dict]] | None = None,
    image_id: str | None = None,
    payload: dict | None = None,
) -> Path:
    task_type = {"seg": "SEG", "det": "DET", "cap": "CAP"}[task]
    package_id = f"{batch_id}__{task}"
    if items is None:
        if image_id is None or payload is None:
            raise ValueError("provide items= or image_id+payload")
        items = [(image_id, payload)]
    doc_items = []
    for item_image_id, item_payload in items:
        doc_items.append(
            {
                "schema_version": SCHEMA_VERSION,
                "batch_id": batch_id,
                "package_id": package_id,
                "task_type": task_type,
                "image_id": item_image_id,
                "diagnosis_text": "original diagnosis",
                "payload": item_payload,
            }
        )
    doc = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "package_id": package_id,
        "task_type": task_type,
        "items": doc_items,
    }
    out = prelabels_task_dir(batch_id, task, data_root=data_root) / "prelabels.json"
    write_json(out, doc)
    return out


def test_to_local_files_url() -> None:
    assert (
        to_local_files_url("task_packages/b/seg/images/a.jpg")
        == f"{LOCAL_FILES_PREFIX}task_packages/b/seg/images/a.jpg"
    )


def test_validate_prelabel_coverage_case1_equal_passes() -> None:
    validate_prelabel_coverage(["a", "b", "c"], ["a", "b", "c"])


def test_validate_prelabel_coverage_case2_missing() -> None:
    with pytest.raises(ValueError, match="Missing prelabels") as exc:
        validate_prelabel_coverage(["a", "b", "c"], ["a", "b"])
    assert "c" in str(exc.value)
    assert "Unknown prelabels" not in str(exc.value)


def test_validate_prelabel_coverage_case3_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown prelabels") as exc:
        validate_prelabel_coverage(["a", "b"], ["a", "b", "c"])
    assert "c" in str(exc.value)
    assert "Missing prelabels" not in str(exc.value)


def test_validate_prelabel_coverage_case4_order_independent() -> None:
    validate_prelabel_coverage(["a", "b", "c"], ["c", "a", "b"])


def test_build_cap_writes_tasks_json_and_local_files_url(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "model caption"},
    )

    out = build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    assert out.name == TASKS_JSON_NAME
    assert out.is_file()

    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert len(tasks) == 1
    image_url = tasks[0]["data"]["image"]
    assert image_url.startswith(LOCAL_FILES_PREFIX)
    assert "task_packages/demo_batch/cap/images/" in image_url
    assert image_id in image_url
    assert tasks[0]["predictions"][0]["result"][0]["value"]["text"] == [
        "model caption"
    ]


def test_build_det_includes_rectangle_predictions(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "det", [image_id], size=(100, 50))
    _write_prelabels(
        data_root,
        batch_id,
        "det",
        image_id=image_id,
        payload={"bboxes": [{"x": 10.0, "y": 5.0, "width": 20.0, "height": 10.0}]},
    )

    out = build_ls_import_tasks(batch_id, TaskType.DET, data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    result = tasks[0]["predictions"][0]["result"]
    assert len(result) == 1
    assert result[0]["type"] == "rectanglelabels"
    assert result[0]["original_width"] == 100
    assert result[0]["original_height"] == 50
    assert tasks[0]["data"]["image"].startswith(LOCAL_FILES_PREFIX)


def test_build_seg_with_mask_emits_brush(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "seg", [image_id], size=(4, 4))
    pre_dir = prelabels_task_dir(batch_id, "seg", data_root=data_root)
    mask_ref = f"masks/{image_id}.png"
    _write_mask(
        pre_dir / "masks" / f"{image_id}.png",
        [
            [1, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 0, 0],
        ],
    )
    _write_prelabels(
        data_root,
        batch_id,
        "seg",
        image_id=image_id,
        payload={"mask_ref": mask_ref},
    )

    out = build_ls_import_tasks(batch_id, "seg", data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert tasks[0]["data"]["mask_ref"] == mask_ref
    assert len(tasks[0]["predictions"][0]["result"]) == 2
    assert tasks[0]["predictions"][0]["result"][0]["value"]["format"] == "rle"


def test_ls_import_coverage_missing_prelabel_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    ids = ["a", "b", "c"]
    _seed_package(data_root, batch_id, "cap", ids)
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        items=[
            ("a", {"caption": "ca"}),
            ("b", {"caption": "cb"}),
        ],
    )
    with pytest.raises(ValueError, match="Missing prelabels") as exc:
        build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    assert "c" in str(exc.value)


def test_ls_import_coverage_unknown_prelabel_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    _seed_package(data_root, batch_id, "cap", ["a", "b"])
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        items=[
            ("a", {"caption": "ca"}),
            ("b", {"caption": "cb"}),
            ("c", {"caption": "cc"}),
        ],
    )
    with pytest.raises(ValueError, match="Unknown prelabels") as exc:
        build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    assert "c" in str(exc.value)


def test_ls_import_coverage_order_independent(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    _seed_package(data_root, batch_id, "cap", ["a", "b", "c"])
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        items=[
            ("c", {"caption": "cc"}),
            ("a", {"caption": "ca"}),
            ("b", {"caption": "cb"}),
        ],
    )
    out = build_ls_import_tasks(batch_id, "cap", data_root=data_root)
    tasks = json.loads(out.read_text(encoding="utf-8"))
    assert {t["data"]["image_id"] for t in tasks} == {"a", "b", "c"}


def test_missing_prelabels_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    with pytest.raises(ValueError, match="prelabels.json not found"):
        build_ls_import_tasks("demo_batch", "cap", data_root=data_root)


def test_missing_package_manifest_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "x"},
    )
    with pytest.raises(ValueError, match="task package manifest not found"):
        build_ls_import_tasks(batch_id, "cap", data_root=data_root)


def test_missing_image_raises_with_image_id(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _write_package_manifest(data_root, batch_id, "cap", [image_id])
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "x"},
    )
    with pytest.raises(ValueError, match="demo_batch__000001"):
        build_ls_import_tasks(batch_id, "cap", data_root=data_root)


def test_seg_missing_mask_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "seg", [image_id], size=(4, 4))
    _write_prelabels(
        data_root,
        batch_id,
        "seg",
        image_id=image_id,
        payload={"mask_ref": "masks/missing.png"},
    )
    with pytest.raises(ValueError, match="mask file not found"):
        build_ls_import_tasks(batch_id, "seg", data_root=data_root)


def test_local_root_override_changes_relative_segment(tmp_path: Path) -> None:
    data_root = tmp_path / "workspace" / "data"
    local_root = tmp_path / "workspace"
    batch_id = "demo_batch"
    image_id = "demo_batch__000001"
    _seed_package(data_root, batch_id, "cap", [image_id])
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "x"},
    )

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
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "x"},
    )
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
    _write_prelabels(
        data_root,
        batch_id,
        "cap",
        image_id=image_id,
        payload={"caption": "cli caption"},
    )
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
