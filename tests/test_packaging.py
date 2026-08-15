"""Tests for T1.4 task package image splitting (no package_id / no manifest)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from mma.common.ids import generate_package_id
from mma.common.models import SampleItem, TaskPackage, TaskType
from mma.common.paths import task_package_dir
from mma.packaging.build_task_packages import (
    build_task_packages,
    write_task_package_manifest,
)
from mma.packaging.split_task_packages import (
    load_processed_items,
    split_task_packages,
)
from mma.preprocess.build_processed import build_processed_batch

_MIN_JPEG = bytes(
    [
        0xFF,
        0xD8,
        0xFF,
        0xE0,
        0x00,
        0x10,
        0x4A,
        0x46,
        0x49,
        0x46,
        0x00,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0xFF,
        0xDB,
        0x00,
        0x43,
        0x00,
        *([0x08] * 64),
        0xFF,
        0xC0,
        0x00,
        0x0B,
        0x08,
        0x00,
        0x01,
        0x00,
        0x01,
        0x01,
        0x01,
        0x11,
        0x00,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x03,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x10,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFF,
        0xDA,
        0x00,
        0x08,
        0x01,
        0x01,
        0x00,
        0x00,
        0x3F,
        0x00,
        0x7F,
        0xFF,
        0xD9,
    ]
)


def _write_jpeg(path: Path) -> None:
    path.write_bytes(_MIN_JPEG)


def _write_excel(path: Path, rows: list[tuple[str, str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["image_name", "diagnosis_text"])
    for image_name, diagnosis_text in rows:
        sheet.append([image_name, diagnosis_text])
    workbook.save(path)


def _prepare_processed(tmp_path: Path, batch_id: str = "batch_a") -> Path:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    _write_jpeg(images / "b.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "text-a"),
            ("b.jpg", "text-b"),
        ],
    )
    data_root = tmp_path / "data"
    return build_processed_batch(
        batch_id,
        images,
        excel,
        data_root=data_root,
    )


def test_split_task_packages_copies_full_sets(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")

    result = split_task_packages("batch_a", data_root=data_root)

    assert set(result) == {TaskType.SEG, TaskType.DET, TaskType.CAP}
    for task_type, samples in result.items():
        assert len(samples) == 2
        assert all(isinstance(s, SampleItem) for s in samples)
        package_dir = task_package_dir("batch_a", task_type, data_root=data_root)
        images_dir = package_dir / "images"
        assert images_dir.is_dir()
        copied = sorted(p.name for p in images_dir.iterdir() if p.is_file())
        assert copied == [
            "batch_a__000001.jpg",
            "batch_a__000002.jpg",
        ]
        assert not (package_dir / "manifest.json").exists()


def test_split_task_packages_sample_fields_consistent(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")

    result = split_task_packages("batch_a", data_root=data_root)
    seg = result[TaskType.SEG]
    det = result[TaskType.DET]
    cap = result[TaskType.CAP]

    assert seg == det == cap
    assert seg[0].image_id == "batch_a__000001"
    assert seg[0].image_path == "images/batch_a__000001.jpg"
    assert seg[0].diagnosis_text == "text-a"
    assert seg[1].image_path == "images/batch_a__000002.jpg"


def test_split_task_packages_copies_file_bytes(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    processed_dir = _prepare_processed(tmp_path, "batch_a")
    records = load_processed_items(processed_dir)
    source_bytes = Path(records[0].image_path).read_bytes()

    split_task_packages("batch_a", data_root=data_root)
    copied = (
        data_root
        / "task_packages"
        / "batch_a"
        / "seg"
        / "images"
        / "batch_a__000001.jpg"
    )
    assert copied.read_bytes() == source_bytes


def test_split_task_packages_rerun_overwrites(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")
    first = split_task_packages("batch_a", data_root=data_root)
    second = split_task_packages("batch_a", data_root=data_root)
    assert first == second
    assert (
        data_root / "task_packages" / "batch_a" / "det" / "images" / "batch_a__000001.jpg"
    ).is_file()


def test_split_rerun_removes_orphan_when_processed_shrinks(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    processed_dir = _prepare_processed(tmp_path, "batch_a")
    split_task_packages("batch_a", data_root=data_root)

    records = load_processed_items(processed_dir)
    kept = records[0]
    (processed_dir / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "batch_a",
                "items": [
                    {
                        "image_id": kept.image_id,
                        "image_path": kept.image_path,
                        "diagnosis_text": kept.diagnosis_text,
                        "source_image_name": kept.source_image_name,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = split_task_packages("batch_a", data_root=data_root)
    expected_name = f"{kept.image_id}.jpg"
    for task_type, samples in result.items():
        assert len(samples) == 1
        assert samples[0].image_id == kept.image_id
        images_dir = task_package_dir("batch_a", task_type, data_root=data_root) / (
            "images"
        )
        names = sorted(p.name for p in images_dir.iterdir() if p.is_file())
        assert names == [expected_name]
        assert not (images_dir / "batch_a__000002.jpg").exists()


def test_split_rerun_removes_old_suffix_on_extension_change(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    processed_dir = _prepare_processed(tmp_path, "batch_a")
    split_task_packages("batch_a", data_root=data_root)

    records = load_processed_items(processed_dir)
    first = records[0]
    jpeg_source = Path(first.image_path)
    jpeg_bytes = jpeg_source.read_bytes()
    new_source = jpeg_source.with_suffix(".jpeg")
    new_source.write_bytes(jpeg_bytes)

    items = [
        {
            "image_id": first.image_id,
            "image_path": str(new_source),
            "diagnosis_text": first.diagnosis_text,
            "source_image_name": new_source.name,
        }
    ]
    for record in records[1:]:
        items.append(
            {
                "image_id": record.image_id,
                "image_path": record.image_path,
                "diagnosis_text": record.diagnosis_text,
                "source_image_name": record.source_image_name,
            }
        )
    (processed_dir / "manifest.json").write_text(
        json.dumps(
            {"batch_id": "batch_a", "items": items},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    split_task_packages("batch_a", data_root=data_root)
    for task_type in (TaskType.SEG, TaskType.DET, TaskType.CAP):
        images_dir = task_package_dir("batch_a", task_type, data_root=data_root) / (
            "images"
        )
        assert (images_dir / f"{first.image_id}.jpeg").is_file()
        assert not (images_dir / f"{first.image_id}.jpg").exists()
        names = sorted(p.name for p in images_dir.iterdir() if p.is_file())
        assert names == [
            f"{first.image_id}.jpeg",
            "batch_a__000002.jpg",
        ]


def test_split_rerun_removes_stray_files_in_images(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")
    split_task_packages("batch_a", data_root=data_root)

    for task_type in (TaskType.SEG, TaskType.DET, TaskType.CAP):
        images_dir = task_package_dir("batch_a", task_type, data_root=data_root) / (
            "images"
        )
        (images_dir / "readme.txt").write_text("stray\n", encoding="utf-8")
        _write_jpeg(images_dir / "orphan_extra.jpg")

    split_task_packages("batch_a", data_root=data_root)
    for task_type in (TaskType.SEG, TaskType.DET, TaskType.CAP):
        images_dir = task_package_dir("batch_a", task_type, data_root=data_root) / (
            "images"
        )
        names = sorted(p.name for p in images_dir.iterdir() if p.is_file())
        assert names == [
            "batch_a__000001.jpg",
            "batch_a__000002.jpg",
        ]


def test_split_images_subdir_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")
    split_task_packages("batch_a", data_root=data_root)

    nested = (
        data_root / "task_packages" / "batch_a" / "seg" / "images" / "extra"
    )
    nested.mkdir()
    (nested / "x.txt").write_text("nested\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected subdirectory"):
        split_task_packages("batch_a", data_root=data_root)


def test_build_task_packages_rerun_orphan_removed(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    processed_dir = _prepare_processed(tmp_path, "batch_a")
    build_task_packages("batch_a", data_root=data_root)

    records = load_processed_items(processed_dir)
    kept = records[0]
    (processed_dir / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "batch_a",
                "items": [
                    {
                        "image_id": kept.image_id,
                        "image_path": kept.image_path,
                        "diagnosis_text": kept.diagnosis_text,
                        "source_image_name": kept.source_image_name,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    packages = build_task_packages("batch_a", data_root=data_root)
    for task_type, package in packages.items():
        assert len(package.samples) == 1
        package_dir = task_package_dir("batch_a", task_type, data_root=data_root)
        names = sorted(
            p.name for p in (package_dir / "images").iterdir() if p.is_file()
        )
        assert names == [f"{kept.image_id}.jpg"]
        payload = json.loads(
            (package_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert len(payload["samples"]) == 1
        assert payload["samples"][0]["image_id"] == kept.image_id


def test_split_missing_processed_dir_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="processed batch directory"):
        split_task_packages("missing_batch", data_root=tmp_path / "data")


def test_load_processed_missing_manifest_fails(tmp_path: Path) -> None:
    processed = tmp_path / "processed" / "batch_a"
    processed.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        load_processed_items(processed)


def test_split_missing_source_image_fails(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    processed = data_root / "processed" / "batch_a"
    processed.mkdir(parents=True)
    (processed / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "batch_a",
                "items": [
                    {
                        "image_id": "batch_a__000001",
                        "image_path": str(tmp_path / "does_not_exist.jpg"),
                        "diagnosis_text": "x",
                        "source_image_name": "a.jpg",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source image not found"):
        split_task_packages("batch_a", data_root=data_root)


def test_split_rejects_invalid_batch_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        split_task_packages("bad/id", data_root=tmp_path / "data")


def test_generate_package_id_format() -> None:
    assert generate_package_id("batch_a", TaskType.SEG) == "batch_a__seg"
    assert generate_package_id("batch_a", "DET") == "batch_a__det"
    assert generate_package_id("batch_a", "cap") == "batch_a__cap"


def test_build_task_packages_end_to_end(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")

    packages = build_task_packages("batch_a", data_root=data_root)

    assert set(packages) == {TaskType.SEG, TaskType.DET, TaskType.CAP}
    package_ids = {p.package_id for p in packages.values()}
    assert package_ids == {"batch_a__seg", "batch_a__det", "batch_a__cap"}

    for task_type, package in packages.items():
        assert isinstance(package, TaskPackage)
        assert package.batch_id == "batch_a"
        assert package.task_type is task_type
        assert len(package.samples) == 2

        package_dir = task_package_dir("batch_a", task_type, data_root=data_root)
        manifest_path = package_dir / "manifest.json"
        assert manifest_path.is_file()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["package_id"] == package.package_id
        assert payload["task_type"] == task_type.value
        assert payload["batch_id"] == "batch_a"
        assert len(payload["samples"]) == 2
        assert payload["samples"][0]["image_path"].startswith("images/")
        for sample in payload["samples"]:
            assert (package_dir / sample["image_path"]).is_file()


def test_build_task_packages_rerun_overwrites_manifest(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _prepare_processed(tmp_path, "batch_a")
    first = build_task_packages("batch_a", data_root=data_root)
    second = build_task_packages("batch_a", data_root=data_root)
    assert first[TaskType.SEG].package_id == second[TaskType.SEG].package_id
    assert (
        data_root / "task_packages" / "batch_a" / "seg" / "manifest.json"
    ).is_file()


def test_write_task_package_manifest_missing_image_fails(tmp_path: Path) -> None:
    package_dir = tmp_path / "seg"
    (package_dir / "images").mkdir(parents=True)
    package = TaskPackage(
        package_id="batch_a__seg",
        task_type=TaskType.SEG,
        samples=(
            SampleItem(
                image_id="batch_a__000001",
                image_path="images/missing.jpg",
                diagnosis_text="x",
            ),
        ),
        batch_id="batch_a",
    )
    with pytest.raises(ValueError, match="package image missing"):
        write_task_package_manifest(package, package_dir)
