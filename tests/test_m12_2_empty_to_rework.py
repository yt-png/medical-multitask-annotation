"""M12.2 gate: confirmed empty / missing task payload → ``rework/``."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
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


def _assert_only_in_rework(
    normal_path: Path,
    rework_path: Path,
    *,
    image_id: str,
) -> list[dict]:
    assert read_json(normal_path) == []
    rework = read_json(rework_path)
    assert len(rework) == 1
    assert rework[0]["image_id"] == image_id
    assert rework[0]["human_confirmed"] is True
    assert rework[0]["needs_rework"] is False
    return rework


def test_m12_2_cap_confirmed_empty_caption_goes_rework(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "cap.json",
        [
            {
                "data": {
                    "image_id": "img-cap-empty",
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
                                "value": {"text": [""]},
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
    rework = _assert_only_in_rework(
        normal_path, rework_path, image_id="img-cap-empty"
    )
    assert rework[0]["annotation"]["caption"] == ""


def test_m12_2_det_confirmed_empty_boxes_goes_rework(tmp_path: Path) -> None:
    images = tmp_path / "task_packages" / "batch1" / "det" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (200, 100), color=(1, 2, 3)).save(
        images / "img-det-empty.jpg"
    )
    export = _write_export(
        tmp_path / "det.json",
        [
            {
                "data": {
                    "image_id": "img-det-empty",
                    "package_id": "batch1__det",
                    "diagnosis_text": "diag",
                },
                "annotations": [
                    {
                        "id": 1,
                        "was_cancelled": False,
                        "updated_at": "2026-08-11T00:00:00.000000Z",
                        "result": [
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
    rework = _assert_only_in_rework(
        normal_path, rework_path, image_id="img-det-empty"
    )
    assert rework[0]["annotation"]["bboxes"] == []


def test_m12_2_seg_confirmed_empty_geometry_goes_rework(tmp_path: Path) -> None:
    export = _write_export(
        tmp_path / "seg.json",
        [
            {
                "data": {
                    "image_id": "img-seg-empty",
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
                                    "rle": [],
                                    "brushlabels": [],
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
    rework = _assert_only_in_rework(
        normal_path, rework_path, image_id="img-seg-empty"
    )
    assert rework[0]["annotation"]["has_foreground"] is False
