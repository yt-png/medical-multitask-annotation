"""Tests for LS raw result side-channel extraction (S2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mma.common.models import TaskType
from mma.exporters import extract_ls_raw_results, extract_ls_raw_results_data


def _task(
    *,
    image_id: str,
    result: list[dict],
    cancelled: bool = False,
    updated_at: str = "2026-08-11T00:00:00.000000Z",
    ann_id: int = 1,
) -> dict:
    return {
        "data": {"image_id": image_id, "package_id": "pkg"},
        "annotations": [
            {
                "id": ann_id,
                "was_cancelled": cancelled,
                "updated_at": updated_at,
                "result": result,
            }
        ],
    }


def test_extract_raw_results_deepcopy_and_keys() -> None:
    brush = {
        "from_name": "seg_mask",
        "type": "brushlabels",
        "value": {"format": "rle", "rle": [1, 2, 3], "brushlabels": ["lesion"]},
    }
    choice = {
        "from_name": "human_confirmed",
        "type": "choices",
        "value": {"choices": ["yes"]},
    }
    data = [_task(image_id="img-1", result=[brush, choice])]
    by_id = extract_ls_raw_results_data(data, task_type=TaskType.SEG)
    assert set(by_id) == {"img-1"}
    assert len(by_id["img-1"]) == 2
    assert by_id["img-1"][0]["value"]["rle"] == [1, 2, 3]

    by_id["img-1"][0]["value"]["rle"].append(99)
    assert brush["value"]["rle"] == [1, 2, 3]


def test_extract_skips_cancelled_uses_latest() -> None:
    data = [
        {
            "data": {"image_id": "img-a"},
            "annotations": [
                {
                    "id": 1,
                    "was_cancelled": True,
                    "updated_at": "2026-08-12T00:00:00.000000Z",
                    "result": [
                        {
                            "from_name": "cap_text",
                            "type": "textarea",
                            "value": {"text": ["cancelled"]},
                        }
                    ],
                },
                {
                    "id": 2,
                    "was_cancelled": False,
                    "updated_at": "2026-08-11T00:00:00.000000Z",
                    "result": [
                        {
                            "from_name": "cap_text",
                            "type": "textarea",
                            "value": {"text": ["kept"]},
                        }
                    ],
                },
            ],
        }
    ]
    by_id = extract_ls_raw_results_data(data, task_type=TaskType.CAP)
    assert by_id["img-a"][0]["value"]["text"] == ["kept"]


def test_extract_duplicate_image_id_raises() -> None:
    result = [
        {
            "from_name": "cap_text",
            "type": "textarea",
            "value": {"text": ["x"]},
        }
    ]
    data = [
        _task(image_id="dup", result=result),
        _task(image_id="dup", result=result, ann_id=2),
    ]
    with pytest.raises(ValueError, match="duplicate image_id"):
        extract_ls_raw_results_data(data, task_type=TaskType.CAP)


def test_extract_reads_file(tmp_path: Path) -> None:
    payload = [
        _task(
            image_id="file-1",
            result=[
                {
                    "from_name": "cap_text",
                    "type": "textarea",
                    "value": {"text": ["from file"]},
                }
            ],
        )
    ]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    by_id = extract_ls_raw_results(path, task_type=TaskType.CAP)
    assert by_id["file-1"][0]["value"]["text"] == ["from file"]
