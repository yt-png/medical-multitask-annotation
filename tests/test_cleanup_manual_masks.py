"""Tests for cleanup of unreferenced SEG manual_masks files."""

from __future__ import annotations

from pathlib import Path

from mma.common.io import write_json
from mma.common.models import SegAnnotation, TaskAnnotationResult, TaskType
from mma.common.paths import results_current_dir, results_manual_masks_dir
from mma.converters.seg_brush import manual_mask_filename, manual_mask_ref
from mma.exporters import (
    apply_current_from_export,
    cleanup_unreferenced_manual_masks,
    load_current,
    overwrite_current,
)
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME


def _seg_current(
    image_id: str,
    *,
    mask_ref: str,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=mask_ref),
        human_confirmed=True,
        needs_rework=False,
        package_id="batch1__seg",
    )


def _write_manual_png(mask_dir: Path, image_id: str) -> Path:
    mask_dir.mkdir(parents=True, exist_ok=True)
    path = mask_dir / manual_mask_filename(image_id)
    path.write_bytes(b"png")
    return path


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _seg_export_task(
    *,
    image_id: str,
    mask_ref: str,
    include_brush: bool,
) -> dict:
    from mma.converters.seg_brush import mask_to_ls_rle

    results: list[dict] = []
    if include_brush:
        results.append(
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "original_width": 2,
                "original_height": 2,
                "value": {
                    "format": "rle",
                    "rle": mask_to_ls_rle([[1, 0], [0, 1]]),
                    "brushlabels": ["lesion"],
                },
            }
        )
    else:
        # Explicit empty clear marker supplies size for empty manual mask.
        results.append(
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "original_width": 2,
                "original_height": 2,
                "value": {
                    "format": "rle",
                    "rle": [],
                    "brushlabels": [],
                },
            }
        )
    results.append(_choice("human_confirmed", "yes"))
    results.append(_choice("needs_rework", "no"))
    return {
        "data": {
            "image_id": image_id,
            "package_id": "batch1__seg",
            "mask_ref": mask_ref,
            "diagnosis_text": "diag",
        },
        "annotations": [
            {
                "id": 1,
                "was_cancelled": False,
                "updated_at": "2026-08-11T00:00:00.000000Z",
                "result": results,
            }
        ],
    }


def test_keeps_referenced_manual_mask(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    kept = _write_manual_png(mask_dir, "img-a")
    overwrite_current(
        [_seg_current("img-a", mask_ref=manual_mask_ref("img-a"))],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert deleted == []
    assert kept.is_file()


def test_deletes_when_current_points_to_prelabel(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    stale = _write_manual_png(mask_dir, "img-a")
    overwrite_current(
        [_seg_current("img-a", mask_ref="masks/img-a.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert [p.name for p in deleted] == [manual_mask_filename("img-a")]
    assert not stale.exists()


def test_deletes_orphan_file_not_in_current(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    kept = _write_manual_png(mask_dir, "img-a")
    orphan = _write_manual_png(mask_dir, "orphan")
    overwrite_current(
        [_seg_current("img-a", mask_ref=manual_mask_ref("img-a"))],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert [p.name for p in deleted] == [manual_mask_filename("orphan")]
    assert kept.is_file()
    assert not orphan.exists()


def test_missing_manual_masks_dir_noop(tmp_path: Path) -> None:
    overwrite_current(
        [_seg_current("img-a", mask_ref="masks/a.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert deleted == []


def test_missing_current_noop(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    kept = _write_manual_png(mask_dir, "img-a")
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert deleted == []
    assert kept.is_file()


def test_ignores_non_manual_png(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    mask_dir.mkdir(parents=True, exist_ok=True)
    other = mask_dir / "notes.txt"
    other.write_text("keep", encoding="utf-8")
    plain = mask_dir / "x.png"
    plain.write_bytes(b"png")
    overwrite_current(
        [_seg_current("img-a", mask_ref="masks/a.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert deleted == []
    assert other.is_file()
    assert plain.is_file()


def test_apply_current_seg_empty_geometry_keeps_manual_mask(
    tmp_path: Path,
) -> None:
    """Brush then clear → empty manual mask remains referenced (no prelabel fallback)."""

    export1 = tmp_path / "export1.json"
    write_json(
        export1,
        [
            _seg_export_task(
                image_id="img-a",
                mask_ref="masks/prelabel.png",
                include_brush=True,
            )
        ],
    )
    apply_current_from_export(
        export1,
        batch_id="batch1",
        task="seg",
        data_root=tmp_path,
    )
    manual_path = (
        results_manual_masks_dir("batch1", data_root=tmp_path)
        / manual_mask_filename("img-a")
    )
    assert manual_path.is_file()
    loaded = load_current("batch1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.mask_ref == manual_mask_ref("img-a")
    assert loaded[0].annotation.has_foreground is True

    export2 = tmp_path / "export2.json"
    write_json(
        export2,
        [
            _seg_export_task(
                image_id="img-a",
                mask_ref="masks/prelabel.png",
                include_brush=False,
            )
        ],
    )
    apply_current_from_export(
        export2,
        batch_id="batch1",
        task="seg",
        data_root=tmp_path,
    )
    loaded2 = load_current("batch1", TaskType.SEG, data_root=tmp_path)
    assert loaded2[0].annotation.mask_ref == manual_mask_ref("img-a")
    assert loaded2[0].annotation.has_foreground is False
    assert manual_path.is_file()


def test_empty_current_deletes_all_manual_masks(tmp_path: Path) -> None:
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    stale = _write_manual_png(mask_dir, "img-a")
    current_dir = results_current_dir("batch1", TaskType.SEG, data_root=tmp_path)
    write_json(current_dir / ANNOTATIONS_JSON_NAME, [])
    deleted = cleanup_unreferenced_manual_masks("batch1", data_root=tmp_path)
    assert [p.name for p in deleted] == [manual_mask_filename("img-a")]
    assert not stale.exists()
