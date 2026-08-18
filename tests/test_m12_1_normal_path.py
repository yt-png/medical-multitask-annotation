"""M12.1 gate: confirmed human annotation with effective payload → ``normal/``."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.converters.seg_brush import mask_to_ls_rle
from mma.exporters import export_split_from_export


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


def _write_package_manifest(
    data_root: Path,
    task: str,
    image_ids: list[str],
    *,
    batch_id: str = "batch1",
) -> None:
    write_json(
        data_root / "task_packages" / batch_id / task / "manifest.json",
        {
            "package_id": f"{batch_id}__{task}",
            "task_type": task.upper(),
            "batch_id": batch_id,
            "samples": [
                {
                    "image_id": image_id,
                    "image_path": f"images/{image_id}.jpg",
                    "diagnosis_text": "diag",
                }
                for image_id in image_ids
            ],
        },
    )


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


def test_m12_1_cap_confirmed_with_caption_goes_normal(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "cap", ["img-cap-ok"])
    export = _write_export(
        tmp_path / "cap.json",
        [
            {
                "data": {
                    "image_id": "img-cap-ok",
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
                                "value": {"text": ["normal caption"]},
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
        task=TaskType.CAP,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-cap-ok"
    )
    assert normal[0]["annotation"]["caption"] == "normal caption"


def test_m12_1_det_confirmed_with_bbox_goes_normal(tmp_path: Path) -> None:
    images = tmp_path / "task_packages" / "batch1" / "det" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (200, 100), color=(1, 2, 3)).save(images / "img-det-ok.jpg")
    _write_package_manifest(tmp_path, "det", ["img-det-ok"])
    export = _write_export(
        tmp_path / "det.json",
        [
            {
                "data": {
                    "image_id": "img-det-ok",
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
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.DET,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-det-ok"
    )
    assert len(normal[0]["annotation"]["bboxes"]) == 1


def test_m12_1_seg_confirmed_with_foreground_goes_normal(tmp_path: Path) -> None:
    _write_package_manifest(tmp_path, "seg", ["img-seg-ok"])
    rle = mask_to_ls_rle([[1, 0], [0, 1]])
    export = _write_export(
        tmp_path / "seg.json",
        [
            {
                "data": {
                    "image_id": "img-seg-ok",
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
        ],
    )
    normal_path, rework_path = export_split_from_export(
        export,
        batch_id="batch1",
        task=TaskType.SEG,
        data_root=tmp_path,
    )
    normal = _assert_only_in_normal(
        normal_path, rework_path, image_id="img-seg-ok"
    )
    assert normal[0]["annotation"]["has_foreground"] is True
