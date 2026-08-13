"""Tests for apply_current_from_export (P4 apply-current glue)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import write_json
from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import results_current_dir, results_manual_masks_dir, results_task_dir
from mma.exporters import apply_current_from_export, load_current, overwrite_current
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.converters.seg_brush import load_foreground_mask, manual_mask_ref, mask_to_ls_rle


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _cap_task(
    *,
    image_id: str,
    caption: str,
    human: str = "yes",
    rework: str = "no",
    package_id: str = "batch1__cap",
) -> dict:
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
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


def _seg_task(
    *,
    image_id: str,
    mask_ref: str,
    human: str = "yes",
    rework: str = "no",
    package_id: str = "batch1__seg",
    include_brush: bool = True,
    brush_rle: list[int] | None = None,
    original_width: int = 2,
    original_height: int = 2,
) -> dict:
    from mma.converters.seg_brush import mask_to_ls_rle

    results: list[dict] = []
    if include_brush:
        if brush_rle is None:
            brush_rle = mask_to_ls_rle(
                [[1 if (x + y) % 2 == 0 else 0 for x in range(original_width)]
                 for y in range(original_height)]
            )
        results.append(
            {
                "from_name": "seg_mask",
                "to_name": "image",
                "type": "brushlabels",
                "original_width": original_width,
                "original_height": original_height,
                "value": {
                    "format": "rle",
                    "rle": brush_rle,
                    "brushlabels": ["lesion"],
                },
            }
        )
    results.append(_choice("human_confirmed", human))
    results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
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


def _det_task(
    *,
    image_id: str,
    boxes_pct: list[tuple[float, float, float, float]],
    human: str = "yes",
    rework: str = "no",
    package_id: str = "batch1__det",
) -> dict:
    results: list[dict] = []
    for x, y, w, h in boxes_pct:
        results.append(
            {
                "from_name": "det_bbox",
                "to_name": "image",
                "type": "rectanglelabels",
                "value": {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "rectanglelabels": ["object"],
                },
            }
        )
    results.append(_choice("human_confirmed", human))
    results.append(_choice("needs_rework", rework))
    return {
        "data": {
            "image_id": image_id,
            "package_id": package_id,
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


def _write_export(path: Path, tasks: list[dict]) -> Path:
    write_json(path, tasks)
    return path


def _write_det_image(data_root: Path, batch_id: str, image_id: str, size: tuple[int, int]) -> None:
    images = data_root / "task_packages" / batch_id / "det" / "images"
    images.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(10, 20, 30)).save(images / f"{image_id}.jpg")


def test_cap_and_seg_write_current(tmp_path: Path) -> None:
    export_cap = _write_export(
        tmp_path / "cap.json",
        [
            _cap_task(image_id="img-a", caption="c1", rework="yes"),
            _cap_task(image_id="img-b", caption="c2", rework="no"),
        ],
    )
    path = apply_current_from_export(
        export_cap,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    expected = (
        results_current_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    )
    assert path == expected.resolve()
    loaded = load_current("batch1", TaskType.CAP, data_root=tmp_path)
    assert len(loaded) == 2
    assert isinstance(loaded[0].annotation, CapAnnotation)
    assert loaded[0].needs_rework is True
    assert loaded[1].needs_rework is False

    export_seg = _write_export(
        tmp_path / "seg.json",
        [_seg_task(image_id="img-a", mask_ref="masks/img-a.png")],
    )
    apply_current_from_export(
        export_seg,
        batch_id="batch1",
        task=TaskType.SEG,
        data_root=tmp_path,
    )
    seg = load_current("batch1", TaskType.SEG, data_root=tmp_path)
    assert len(seg) == 1
    assert seg[0].annotation.mask_ref == manual_mask_ref("img-a")
    mask_file = results_manual_masks_dir("batch1", data_root=tmp_path) / (
        "img-a_manual.png"
    )
    assert mask_file.is_file()


def test_seg_brush_writes_manual_mask_ref(tmp_path: Path) -> None:
    binary = [
        [1, 0, 1],
        [0, 1, 0],
        [0, 0, 1],
    ]
    export = _write_export(
        tmp_path / "seg.json",
        [
            _seg_task(
                image_id="img-brush",
                mask_ref="masks/prelabel.png",
                brush_rle=mask_to_ls_rle(binary),
                original_width=3,
                original_height=3,
            )
        ],
    )
    apply_current_from_export(
        export,
        batch_id="batch1",
        task="seg",
        data_root=tmp_path,
    )
    loaded = load_current("batch1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.mask_ref == "manual_masks/img-brush_manual.png"
    out = results_manual_masks_dir("batch1", data_root=tmp_path) / (
        "img-brush_manual.png"
    )
    decoded, w, h = load_foreground_mask(out)
    assert (w, h) == (3, 3)
    assert decoded == binary


def test_seg_without_brush_keeps_prelabel_mask_ref(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "seg.json",
        [
            _seg_task(
                image_id="img-nb",
                mask_ref="masks/keep.png",
                include_brush=False,
            )
        ],
    )
    apply_current_from_export(
        export,
        batch_id="batch1",
        task="seg",
        data_root=tmp_path,
    )
    loaded = load_current("batch1", TaskType.SEG, data_root=tmp_path)
    assert loaded[0].annotation.mask_ref == "masks/keep.png"
    mask_dir = results_manual_masks_dir("batch1", data_root=tmp_path)
    assert not mask_dir.exists() or list(mask_dir.glob("*")) == []


def test_det_uses_task_package_image_size(tmp_path: Path) -> None:
    _write_det_image(tmp_path, "batch1", "img-a", (200, 100))
    export = _write_export(
        tmp_path / "det.json",
        [
            _det_task(
                image_id="img-a",
                boxes_pct=[(10.0, 20.0, 25.0, 50.0)],
            )
        ],
    )
    apply_current_from_export(
        export,
        batch_id="batch1",
        task="det",
        data_root=tmp_path,
    )
    loaded = load_current("batch1", TaskType.DET, data_root=tmp_path)
    assert len(loaded) == 1
    assert isinstance(loaded[0].annotation, DetAnnotation)
    box = loaded[0].annotation.bboxes[0]
    assert box.x == pytest.approx(20.0)
    assert box.y == pytest.approx(20.0)
    assert box.width == pytest.approx(50.0)
    assert box.height == pytest.approx(50.0)


def test_det_missing_package_image_fails(tmp_path: Path) -> None:
    images = tmp_path / "task_packages" / "batch1" / "det" / "images"
    images.mkdir(parents=True, exist_ok=True)
    export = _write_export(
        tmp_path / "det.json",
        [_det_task(image_id="missing", boxes_pct=[(0.0, 0.0, 10.0, 10.0)])],
    )
    with pytest.raises(ValueError, match="package image missing"):
        apply_current_from_export(
            export,
            batch_id="batch1",
            task="det",
            data_root=tmp_path,
        )


def test_same_image_id_second_apply_overwrites(tmp_path: Path) -> None:
    first = _write_export(
        tmp_path / "cap1.json",
        [_cap_task(image_id="img-a", caption="old", rework="yes")],
    )
    apply_current_from_export(
        first,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    second = _write_export(
        tmp_path / "cap2.json",
        [_cap_task(image_id="img-a", caption="new", rework="no")],
    )
    apply_current_from_export(
        second,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    loaded = load_current("batch1", TaskType.CAP, data_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].annotation.caption == "new"
    assert loaded[0].needs_rework is False


def test_empty_export_is_noop(tmp_path: Path) -> None:
    seed = overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-a",
                task_type=TaskType.CAP,
                annotation=CapAnnotation(caption="keep"),
                human_confirmed=True,
                needs_rework=False,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    assert seed.is_file()
    empty = _write_export(tmp_path / "empty.json", [])
    out = apply_current_from_export(
        empty,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    assert out == seed
    loaded = load_current("batch1", TaskType.CAP, data_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0].annotation.caption == "keep"


def test_missing_export_file_and_bad_batch_id(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        apply_current_from_export(
            missing,
            batch_id="batch1",
            task="cap",
            data_root=tmp_path,
        )
    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="x")],
    )
    with pytest.raises(ValueError, match="batch_id"):
        apply_current_from_export(
            export,
            batch_id="bad/id",
            task="cap",
            data_root=tmp_path,
        )


def test_apply_refreshes_normal_rework_from_current(tmp_path: Path) -> None:
    from mma.common.io import read_json

    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="x", rework="yes")],
    )
    apply_current_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    task_dir = results_task_dir("batch1", TaskType.CAP, data_root=tmp_path)
    assert (task_dir / "current" / ANNOTATIONS_JSON_NAME).is_file()
    normal = read_json(task_dir / "normal" / ANNOTATIONS_JSON_NAME)
    rework = read_json(task_dir / "rework" / ANNOTATIONS_JSON_NAME)
    assert normal == []
    assert [x["image_id"] for x in rework] == ["img-a"]


def test_multi_round_rework_moves_sample_into_normal(tmp_path: Path) -> None:
    """Subset rework export must update current and full-rebuild normal."""

    from mma.common.io import read_json

    round1 = _write_export(
        tmp_path / "round1.json",
        [
            _cap_task(image_id="img-ok", caption="ok", rework="no"),
            _cap_task(image_id="img-fix", caption="bad", rework="yes"),
        ],
    )
    apply_current_from_export(
        round1,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    task_dir = results_task_dir("batch1", TaskType.CAP, data_root=tmp_path)
    assert [x["image_id"] for x in read_json(task_dir / "normal" / ANNOTATIONS_JSON_NAME)] == [
        "img-ok"
    ]
    assert [x["image_id"] for x in read_json(task_dir / "rework" / ANNOTATIONS_JSON_NAME)] == [
        "img-fix"
    ]

    round2 = _write_export(
        tmp_path / "round2.json",
        [_cap_task(image_id="img-fix", caption="fixed", rework="no")],
    )
    apply_current_from_export(
        round2,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    normal = read_json(task_dir / "normal" / ANNOTATIONS_JSON_NAME)
    rework = read_json(task_dir / "rework" / ANNOTATIONS_JSON_NAME)
    assert {x["image_id"] for x in normal} == {"img-ok", "img-fix"}
    assert {x["annotation"]["caption"] for x in normal} == {"ok", "fixed"}
    assert rework == []
    current = load_current("batch1", TaskType.CAP, data_root=tmp_path)
    by_id = {item.image_id: item for item in current}
    assert by_id["img-fix"].annotation.caption == "fixed"
    assert by_id["img-fix"].needs_rework is False
