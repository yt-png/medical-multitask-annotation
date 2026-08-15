"""Tests for ``parse_export_round_from_path`` and export_round wiring."""

from __future__ import annotations

from pathlib import Path

from mma.common.models import CapAnnotation, TaskType
from mma.common.paths import parse_export_round_from_path
from mma.exporters.parse_ls_export import parse_ls_export, parse_ls_export_data


def _choice(from_name: str, value: str) -> dict:
    return {
        "from_name": from_name,
        "to_name": "image",
        "type": "choices",
        "value": {"choices": [value]},
    }


def _cap_task(*, image_id: str = "img-1", caption: str = "hello") -> dict:
    return {
        "data": {
            "image_id": image_id,
            "package_id": "demo_batch__cap",
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
                    {
                        "from_name": "cap_text",
                        "to_name": "image",
                        "type": "textarea",
                        "value": {"text": [caption]},
                    },
                ],
            }
        ],
    }


def test_round_001_parses_to_1() -> None:
    assert (
        parse_export_round_from_path(
            "data/ls_export/batch/cap/round_001/export.json"
        )
        == 1
    )
    assert (
        parse_export_round_from_path(
            Path("data/ls_export/batch/det/round_012/export.json")
        )
        == 12
    )


def test_no_round_dir_returns_none() -> None:
    assert (
        parse_export_round_from_path(
            "data/ls_export/batch/cap/export.json"
        )
        is None
    )
    assert parse_export_round_from_path(Path("export.json")) is None
    assert (
        parse_export_round_from_path(
            "data/ls_export/batch/cap/round_x/export.json"
        )
        is None
    )


def test_parse_ls_export_data_includes_export_round() -> None:
    results = parse_ls_export_data(
        [_cap_task()],
        task_type=TaskType.CAP,
        export_round=1,
    )
    assert len(results) == 1
    assert results[0].export_round == 1
    assert isinstance(results[0].annotation, CapAnnotation)


def test_parse_ls_export_data_default_export_round_none() -> None:
    results = parse_ls_export_data([_cap_task()], task_type=TaskType.CAP)
    assert results[0].export_round is None


def test_parse_ls_export_file_uses_export_round(
    tmp_path: Path,
) -> None:
    export_dir = tmp_path / "round_002"
    export_dir.mkdir()
    export_path = export_dir / "export.json"
    export_path.write_text(
        '[{"data":{"image_id":"img-1","package_id":"b__cap","diagnosis_text":"d"},'
        '"annotations":[{"id":1,"was_cancelled":false,'
        '"updated_at":"2026-08-11T00:00:00.000000Z","result":['
        '{"from_name":"human_confirmed","to_name":"image","type":"choices",'
        '"value":{"choices":["yes"]}},'
        '{"from_name":"needs_rework","to_name":"image","type":"choices",'
        '"value":{"choices":["no"]}},'
        '{"from_name":"cap_text","to_name":"image","type":"textarea",'
        '"value":{"text":["c"]}}]}]}]',
        encoding="utf-8",
    )
    round_num = parse_export_round_from_path(export_path)
    assert round_num == 2
    results = parse_ls_export(
        export_path,
        task_type=TaskType.CAP,
        export_round=round_num,
    )
    assert results[0].export_round == 2
