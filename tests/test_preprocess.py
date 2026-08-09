"""Tests for T1.1 image/Excel pairing (no CLI, no image_id, no processed/)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from mma.common.models import ImageTextPair
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
