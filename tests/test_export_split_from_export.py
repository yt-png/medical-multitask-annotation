"""Tests for export_split_from_export (P4 export-split glue)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.common.paths import (
    results_current_dir,
    results_normal_dir,
    results_rework_dir,
    results_task_dir,
)
from mma.exporters import export_split_from_export
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME


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
    rework: str = "no",
    human: str = "yes",
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


def _det_task(
    *,
    image_id: str,
    boxes_pct: list[tuple[float, float, float, float]],
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
    results.append(_choice("human_confirmed", "yes"))
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


def test_mixed_cap_writes_normal_and_rework(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [
            _cap_task(image_id="img-a", caption="ok", rework="no"),
            _cap_task(image_id="img-b", caption="fix", rework="yes"),
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    assert normal_path == (
        results_normal_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    ).resolve()
    assert rework_path == (
        results_rework_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    ).resolve()

    normal = read_json(normal_path)
    rework = read_json(rework_path)
    assert len(normal) == 1
    assert normal[0]["image_id"] == "img-a"
    assert normal[0]["needs_rework"] is False
    assert normal[0]["annotation"]["caption"] == "ok"
    assert len(rework) == 1
    assert rework[0]["image_id"] == "img-b"
    assert rework[0]["needs_rework"] is True
    assert rework[0]["annotation"]["caption"] == "fix"


def test_all_normal_writes_empty_rework_array(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="only", rework="no")],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    assert len(read_json(normal_path)) == 1
    assert read_json(rework_path) == []


def test_all_rework_writes_empty_normal_array(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="bad", rework="yes")],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    assert read_json(normal_path) == []
    assert len(read_json(rework_path)) == 1


def test_unconfirmed_goes_to_rework_not_normal(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [
            _cap_task(
                image_id="img-u1",
                caption="unc-a",
                rework="no",
                human="no",
            ),
            _cap_task(
                image_id="img-u2",
                caption="unc-b",
                rework="yes",
                human="no",
            ),
            _cap_task(image_id="img-ok", caption="ok", rework="no", human="yes"),
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    normal = read_json(normal_path)
    rework = read_json(rework_path)
    assert [x["image_id"] for x in normal] == ["img-ok"]
    assert [x["image_id"] for x in rework] == ["img-u1", "img-u2"]
    assert all(x["human_confirmed"] is False for x in rework)


def test_det_split_uses_task_package_size(tmp_path: Path) -> None:
    images = tmp_path / "task_packages" / "batch1" / "det" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (200, 100), color=(1, 2, 3)).save(images / "img-a.jpg")
    export = _write_export(
        tmp_path / "det.json",
        [
            _det_task(
                image_id="img-a",
                boxes_pct=[(10.0, 20.0, 25.0, 50.0)],
                rework="no",
            )
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="det",
        data_root=tmp_path,
    )
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert len(normal) == 1
    box = normal[0]["annotation"]["bboxes"][0]
    assert box["x"] == pytest.approx(20.0)
    assert box["y"] == pytest.approx(20.0)
    assert box["width"] == pytest.approx(50.0)
    assert box["height"] == pytest.approx(50.0)


def test_missing_export_and_bad_batch_id(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_split_from_export(
            tmp_path / "missing.json",
            batch_id="batch1",
            task="cap",
            data_root=tmp_path,
        )
    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="x")],
    )
    with pytest.raises(ValueError, match="batch_id"):
        export_split_from_export(
            export,
            batch_id="bad/id",
            task="cap",
            data_root=tmp_path,
        )


def test_writes_current_and_full_rebuilds_bundles(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [_cap_task(image_id="img-a", caption="x", rework="yes")],
    )
    export_split_from_export(
        export,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    task_dir = results_task_dir("batch1", TaskType.CAP, data_root=tmp_path)
    assert (task_dir / "normal" / ANNOTATIONS_JSON_NAME).is_file()
    assert (task_dir / "rework" / ANNOTATIONS_JSON_NAME).is_file()
    assert not (task_dir / "pending").exists()
    assert (
        results_current_dir("batch1", TaskType.CAP, data_root=tmp_path)
        / ANNOTATIONS_JSON_NAME
    ).is_file()
    assert not any(task_dir.glob("**/round_*"))


def test_export_split_subset_rework_refreshes_full_normal(tmp_path: Path) -> None:
    round1 = _write_export(
        tmp_path / "round1.json",
        [
            _cap_task(image_id="img-ok", caption="ok", rework="no"),
            _cap_task(image_id="img-fix", caption="bad", rework="yes"),
        ],
    )
    export_split_from_export(
        round1,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    round2 = _write_export(
        tmp_path / "round2.json",
        [_cap_task(image_id="img-fix", caption="fixed", rework="no")],
    )
    normal_path, rework_path = export_split_from_export(
        round2,
        batch_id="batch1",
        task="cap",
        data_root=tmp_path,
    )
    normal = read_json(normal_path)
    assert {x["image_id"] for x in normal} == {"img-ok", "img-fix"}
    assert read_json(rework_path) == []


def test_seg_split_uses_manual_mask_ref(tmp_path: Path) -> None:
    from mma.common.paths import results_manual_masks_dir
    from mma.converters.seg_brush import mask_to_ls_rle, manual_mask_ref

    binary = [[1, 0], [0, 1]]
    rle = mask_to_ls_rle(binary)
    export = _write_export(
        tmp_path / "seg.json",
        [
            {
                "data": {
                    "image_id": "img-a",
                    "package_id": "batch1__seg",
                    "mask_ref": "masks/old.png",
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
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task="seg",
        data_root=tmp_path,
    )
    assert read_json(rework_path) == []
    normal = read_json(normal_path)
    assert normal[0]["annotation"]["mask_ref"] == manual_mask_ref("img-a")
    assert (
        results_manual_masks_dir("batch1", data_root=tmp_path) / "img-a_manual.png"
    ).is_file()
