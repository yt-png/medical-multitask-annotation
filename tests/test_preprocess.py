"""Tests for T1.1 image/Excel pairing (no CLI, no image_id, no processed/)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

import json

from mma.common.ids import generate_image_id
from mma.common.models import ImageRecord, ImageTextPair
from mma.common.paths import processed_batch_dir, validate_batch_id
from mma.preprocess.assign_image_ids import assign_image_ids
from mma.preprocess.build_processed import (
    build_processed_batch,
    write_processed_manifest,
)
from mma.preprocess.load_processed import load_processed_items
from mma.preprocess.pair_images_excel import pair_images_with_excel

# Tiny valid JPEG (1x1) for fixture files.
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


def test_pair_images_with_excel_success(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    _write_jpeg(images / "b.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "findings A"),
            ("b.jpg", "findings B"),
        ],
    )

    pairs = pair_images_with_excel(images, excel, batch_id="batch-demo")

    assert len(pairs) == 2
    assert all(isinstance(p, ImageTextPair) for p in pairs)
    by_name = {p.source_image_name: p for p in pairs}
    assert by_name["a.jpg"].diagnosis_text == "findings A"
    assert by_name["b.jpg"].diagnosis_text == "findings B"
    assert Path(by_name["a.jpg"].image_path).is_absolute()
    assert Path(by_name["a.jpg"].image_path) == (images / "a.jpg").resolve()
    assert by_name["a.jpg"].batch_id == "batch-demo"


def test_pair_without_batch_id(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "only.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(excel, [("only.jpg", "text")])

    pairs = pair_images_with_excel(images, excel)
    assert len(pairs) == 1
    assert pairs[0].batch_id is None


def test_accepts_jpeg_suffix_case_variants(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "upper.JPG")
    _write_jpeg(images / "mixed.JPEG")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("upper.JPG", "u"),
            ("mixed.JPEG", "m"),
        ],
    )

    pairs = pair_images_with_excel(images, excel)
    assert {p.source_image_name for p in pairs} == {"upper.JPG", "mixed.JPEG"}


def test_match_is_case_and_whitespace_insensitive(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "Case.Jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(excel, [("  case.jpg  ", "normalized")])

    pairs = pair_images_with_excel(images, excel)
    assert len(pairs) == 1
    assert pairs[0].source_image_name == "Case.Jpg"
    assert pairs[0].diagnosis_text == "normalized"


def test_empty_diagnosis_text_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(excel, [("a.jpg", "")])

    with pytest.raises(ValueError, match="empty diagnosis_text"):
        pair_images_with_excel(images, excel)


def test_image_without_excel_row_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    _write_jpeg(images / "b.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(excel, [("a.jpg", "only a")])

    with pytest.raises(ValueError, match="images without excel rows"):
        pair_images_with_excel(images, excel)


def test_excel_row_without_image_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "a"),
            ("missing.jpg", "gone"),
        ],
    )

    with pytest.raises(ValueError, match="excel rows without images"):
        pair_images_with_excel(images, excel)


def test_duplicate_excel_image_name_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "first"),
            ("A.JPG", "second"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate image_name"):
        pair_images_with_excel(images, excel)


def test_non_jpg_file_in_directory_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    (images / "extra.png").write_bytes(b"not-a-jpeg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(excel, [("a.jpg", "a")])

    with pytest.raises(ValueError, match="unsupported file"):
        pair_images_with_excel(images, excel)


def test_missing_excel_columns_fails(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    excel = tmp_path / "bad.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["filename", "text"])
    sheet.append(["a.jpg", "x"])
    workbook.save(excel)

    with pytest.raises(ValueError, match="image_name"):
        pair_images_with_excel(images, excel)


def test_missing_paths_fail(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        pair_images_with_excel(tmp_path / "no_dir", tmp_path / "no.xlsx")

    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    with pytest.raises(FileNotFoundError):
        pair_images_with_excel(images, tmp_path / "missing.xlsx")


def test_examples_raw_demo_batch_pairs() -> None:
    """Smoke: documented fake sample under examples/raw can be paired."""

    root = Path(__file__).resolve().parents[1]
    images = root / "examples" / "raw" / "demo_batch" / "images"
    excel = root / "examples" / "raw" / "demo_batch" / "diagnoses.xlsx"
    if not images.is_dir() or not excel.is_file():
        pytest.skip("examples/raw/demo_batch not present")

    pairs = pair_images_with_excel(images, excel, batch_id="demo_batch")
    assert len(pairs) >= 1
    assert all(p.diagnosis_text for p in pairs)


def _sample_pairs(
    *,
    batch_id: str | None = None,
    names: tuple[str, ...] = ("a.jpg", "b.jpg"),
) -> tuple[ImageTextPair, ...]:
    return tuple(
        ImageTextPair(
            image_path=f"/tmp/images/{name}",
            diagnosis_text=f"text-{name}",
            source_image_name=name,
            batch_id=batch_id,
        )
        for name in names
    )


def test_generate_image_id_format() -> None:
    assert generate_image_id("demo_batch", 1) == "demo_batch__000001"
    assert generate_image_id("demo_batch", 12) == "demo_batch__000012"


def test_assign_image_ids_success() -> None:
    pairs = _sample_pairs(batch_id="batch-a")
    records = assign_image_ids(pairs, "batch-a")

    assert len(records) == 2
    assert all(isinstance(r, ImageRecord) for r in records)
    assert records[0].image_id == "batch-a__000001"
    assert records[1].image_id == "batch-a__000002"
    assert records[0].image_path == pairs[0].image_path
    assert records[0].diagnosis_text == pairs[0].diagnosis_text
    assert records[0].source_image_name == "a.jpg"
    assert records[0].batch_id == "batch-a"


def test_assign_image_ids_deterministic() -> None:
    pairs = _sample_pairs()
    first = assign_image_ids(pairs, "batch-a")
    second = assign_image_ids(pairs, "batch-a")
    assert [r.image_id for r in first] == [r.image_id for r in second]


def test_assign_image_ids_unique_within_batch() -> None:
    pairs = _sample_pairs(names=("a.jpg", "b.jpg", "c.jpg"))
    records = assign_image_ids(pairs, "batch-a")
    ids = [r.image_id for r in records]
    assert len(ids) == len(set(ids)) == 3


def test_assign_image_ids_multi_batch_prefix_isolation() -> None:
    """Same source names / sequences in two batches get distinct prefixed IDs."""

    pairs = _sample_pairs(names=("a.jpg", "b.jpg"))
    batch_a = assign_image_ids(pairs, "batch-a")
    batch_b = assign_image_ids(pairs, "batch-b")

    ids_a = [r.image_id for r in batch_a]
    ids_b = [r.image_id for r in batch_b]

    assert ids_a == ["batch-a__000001", "batch-a__000002"]
    assert ids_b == ["batch-b__000001", "batch-b__000002"]
    assert set(ids_a).isdisjoint(set(ids_b))
    assert all(r.batch_id == "batch-a" for r in batch_a)
    assert all(r.batch_id == "batch-b" for r in batch_b)


def test_assign_image_ids_rejects_empty_batch_id() -> None:
    pairs = _sample_pairs()
    with pytest.raises(ValueError, match="batch_id"):
        assign_image_ids(pairs, "")
    with pytest.raises(ValueError, match="batch_id"):
        assign_image_ids(pairs, "   ")


def test_assign_image_ids_rejects_empty_pairs() -> None:
    with pytest.raises(ValueError, match="pairs must not be empty"):
        assign_image_ids((), "batch-a")


def test_assign_image_ids_rejects_duplicate_source_name() -> None:
    pairs = _sample_pairs(names=("A.jpg", "a.jpg"))
    with pytest.raises(ValueError, match="duplicate source_image_name"):
        assign_image_ids(pairs, "batch-a")


def test_assign_image_ids_rejects_mismatched_pair_batch_id() -> None:
    pairs = _sample_pairs(batch_id="other-batch")
    with pytest.raises(ValueError, match="does not match"):
        assign_image_ids(pairs, "batch-a")


def test_assign_image_ids_allows_none_pair_batch_id() -> None:
    pairs = _sample_pairs(batch_id=None)
    records = assign_image_ids(pairs, "batch-a")
    assert all(r.batch_id == "batch-a" for r in records)


def test_validate_batch_id_and_processed_dir(tmp_path: Path) -> None:
    assert validate_batch_id(" batch_1 ") == "batch_1"
    assert processed_batch_dir("batch_1", data_root=tmp_path) == (
        tmp_path / "processed" / "batch_1"
    )
    with pytest.raises(ValueError):
        validate_batch_id("bad/id")
    with pytest.raises(ValueError):
        validate_batch_id("has space")


def test_write_processed_manifest_success(tmp_path: Path) -> None:
    abs_a = str((tmp_path / "a.jpg").resolve())
    abs_b = str((tmp_path / "b.jpg").resolve())
    pairs = (
        ImageTextPair(
            image_path=abs_a,
            diagnosis_text="text-a.jpg",
            source_image_name="a.jpg",
        ),
        ImageTextPair(
            image_path=abs_b,
            diagnosis_text="text-b.jpg",
            source_image_name="b.jpg",
        ),
    )
    records = assign_image_ids(pairs, "batch-a")
    out_dir = tmp_path / "processed" / "batch-a"
    manifest_path = write_processed_manifest(records, out_dir)

    assert manifest_path == out_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch-a"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["image_id"] == "batch-a__000001"
    assert Path(payload["items"][0]["image_path"]).is_absolute()
    assert payload["items"][0]["image_path"] == abs_a
    assert payload["items"][0]["source_image_name"] == "a.jpg"
    assert payload["items"][0]["diagnosis_text"] == "text-a.jpg"


def test_write_processed_manifest_overwrite(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed" / "batch-a"
    first = assign_image_ids(_sample_pairs(names=("a.jpg",)), "batch-a")
    write_processed_manifest(first, out_dir)
    second = assign_image_ids(
        _sample_pairs(names=("a.jpg", "b.jpg")),
        "batch-a",
    )
    write_processed_manifest(second, out_dir)
    payload = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(payload["items"]) == 2


def test_write_processed_manifest_rejects_empty_and_mixed_batch(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="records must not be empty"):
        write_processed_manifest((), tmp_path)

    a = assign_image_ids(_sample_pairs(names=("a.jpg",)), "batch-a")
    b = assign_image_ids(_sample_pairs(names=("b.jpg",)), "batch-b")
    with pytest.raises(ValueError, match="multiple batch_id"):
        write_processed_manifest(a + b, tmp_path)


def test_build_processed_batch_end_to_end(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    _write_jpeg(images / "b.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "findings A"),
            ("b.jpg", "findings B"),
        ],
    )
    data_root = tmp_path / "data"
    out_dir = build_processed_batch(
        "demo_batch",
        images,
        excel,
        data_root=data_root,
    )

    assert out_dir == data_root / "processed" / "demo_batch"
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["batch_id"] == "demo_batch"
    assert [item["image_id"] for item in manifest["items"]] == [
        "demo_batch__000001",
        "demo_batch__000002",
    ]
    for item in manifest["items"]:
        assert Path(item["image_path"]).is_absolute()
        assert Path(item["image_path"]).is_file()
    # Images are referenced, not copied into processed/
    assert not (out_dir / "images").exists()


def test_load_processed_missing_manifest_fails(tmp_path: Path) -> None:
    processed = tmp_path / "processed" / "batch_a"
    processed.mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        load_processed_items(processed)


def test_load_processed_items_roundtrip(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    _write_jpeg(images / "a.jpg")
    _write_jpeg(images / "b.jpg")
    excel = tmp_path / "diagnoses.xlsx"
    _write_excel(
        excel,
        [
            ("a.jpg", "findings A"),
            ("b.jpg", "findings B"),
        ],
    )
    data_root = tmp_path / "data"
    out_dir = build_processed_batch(
        "demo_batch",
        images,
        excel,
        data_root=data_root,
    )

    records = load_processed_items(out_dir)
    assert len(records) == 2
    assert records[0].image_id == "demo_batch__000001"
    assert records[0].diagnosis_text == "findings A"
    assert records[0].source_image_name == "a.jpg"
    assert records[0].batch_id == "demo_batch"
    assert Path(records[0].image_path).is_file()
    assert records[1].image_id == "demo_batch__000002"
    assert records[1].diagnosis_text == "findings B"
