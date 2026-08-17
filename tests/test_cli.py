"""Tests for unified CLI (V1 main flow wired; convert is LEGACY stub)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

from mma.cli import SUBCOMMANDS, TASK_CHOICES, build_parser, main

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


def _prepare_preprocess_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.jpg").write_bytes(_MIN_JPEG)
    excel = tmp_path / "diagnoses.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["image_name", "diagnosis_text"])
    sheet.append(["a.jpg", "text-a"])
    workbook.save(excel)
    data_root = tmp_path / "data"
    return images, excel, data_root


def test_help_lists_all_subcommands() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    for name in SUBCOMMANDS:
        assert name in help_text


def test_main_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["-h"])
    assert exc.value.code == 0


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_subcommand_help_exits_zero(command: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main([command, "-h"])
    assert exc.value.code == 0


def test_all_subcommands_registered() -> None:
    parser = build_parser()
    command_action = next(a for a in parser._actions if a.dest == "command")
    assert command_action.choices is not None
    assert set(command_action.choices.keys()) == set(SUBCOMMANDS)


def test_preprocess_missing_required_args_fails() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["preprocess", "--batch", "b1"])
    assert exc.value.code == 2


def test_invalid_task_fails() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["convert", "--batch", "b1", "--task", "invalid"])
    assert exc.value.code == 2


@pytest.mark.parametrize("task", TASK_CHOICES)
def test_valid_task_accepted_then_legacy_convert_stub(
    task: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["convert", "--batch", "b1", "--task", task])
    assert code == 2
    err = capsys.readouterr().err.lower()
    assert "legacy" in err
    assert "v1" in err
    assert "does not support" in err or "unsupported" in err
    assert "prelabel" in err
    assert "ls-import" in err
    assert "convert" in err


def test_stub_for_convert(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["convert", "--batch", "batch-a", "--task", "cap"])
    assert code == 2
    err = capsys.readouterr().err.lower()
    assert "legacy" in err
    assert "v1" in err
    assert "does not support" in err or "unsupported" in err
    assert "ls-import" in err
    assert "convert" in err


def test_convert_help_marks_legacy() -> None:
    parser = build_parser()
    convert_parser = parser._subparsers._group_actions[0].choices["convert"]
    text = convert_parser.format_help().lower()
    assert "legacy" in text
    assert "v1" in text
    assert "does not support" in text or "unsupported" in text
    assert "ls-import" in text


def test_ls_import_help_describes_empty_task_packages() -> None:
    parser = build_parser()
    ls_parser = parser._subparsers._group_actions[0].choices["ls-import"]
    text = ls_parser.format_help().lower()
    assert "empty" in text
    assert "task_packages" in text
    assert "prediction" in text
    # Must not require preparing prelabels for V1 first-round import.
    assert "must" not in text or "prelabel" not in text
    assert "require" not in text or "prelabel" not in text


def test_rework_import_help_v1_wording() -> None:
    parser = build_parser()
    rw_parser = parser._subparsers._group_actions[0].choices["rework-import"]
    text = rw_parser.format_help().lower()
    assert "previous_annotations" in text
    assert "does not read" in text
    assert "prelabel" in text


def test_export_split_requires_export() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["export-split", "--batch", "b1", "--task", "seg"])
    assert exc.value.code == 2


def test_apply_current_requires_export() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["apply-current", "--batch", "b1", "--task", "cap"])
    assert exc.value.code == 2


def test_rework_import_without_previous_needs_export(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without previous_annotations, omitting --export fails in business logic."""

    code = main(
        [
            "rework-import",
            "--batch",
            "b1",
            "--task",
            "cap",
            "--data-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma rework-import:" in captured.err


def _write_cap_export(path: Path, *, image_id: str = "img-a", caption: str = "hi") -> None:
    payload = [
        {
            "data": {
                "image_id": image_id,
                "package_id": "batch_cli__cap",
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
                        {
                            "from_name": "human_confirmed",
                            "to_name": "image",
                            "type": "choices",
                            "value": {"choices": ["yes"]},
                        },
                        {
                            "from_name": "needs_rework",
                            "to_name": "image",
                            "type": "choices",
                            "value": {"choices": ["no"]},
                        },
                    ],
                }
            ],
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_apply_current_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_root = tmp_path / "data"
    export = tmp_path / "cap_export.json"
    _write_cap_export(export)
    code = main(
        [
            "apply-current",
            "--batch",
            "batch_cli",
            "--task",
            "cap",
            "--export",
            str(export),
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    out_file = (
        data_root / "results" / "batch_cli" / "cap" / "current" / "annotations.json"
    )
    assert out_file.is_file()
    assert str(out_file.resolve()) in captured.out or str(out_file) in captured.out
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload[0]["image_id"] == "img-a"
    assert payload[0]["annotation"]["caption"] == "hi"


def test_apply_current_missing_export(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "apply-current",
            "--batch",
            "batch_cli",
            "--task",
            "cap",
            "--export",
            str(tmp_path / "missing.json"),
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma apply-current:" in captured.err


def test_rework_import_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from PIL import Image

    data_root = tmp_path / "data"
    batch_id = "batch_cli"
    image_id = "img-a"
    package_dir = data_root / "task_packages" / batch_id / "cap"
    images_dir = package_dir / "images"
    images_dir.mkdir(parents=True)
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(images_dir / f"{image_id}.jpg")
    (package_dir / "manifest.json").write_text(
        json.dumps(
            {
                "package_id": f"{batch_id}__cap",
                "task_type": "CAP",
                "batch_id": batch_id,
                "samples": [
                    {
                        "image_id": image_id,
                        "image_path": f"images/{image_id}.jpg",
                        "diagnosis_text": "cli diag",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    export = tmp_path / "cap_export.json"
    payload = [
        {
            "data": {
                "image_id": image_id,
                "package_id": f"{batch_id}__cap",
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
                            "value": {"text": ["need rework"]},
                        },
                        {
                            "from_name": "human_confirmed",
                            "to_name": "image",
                            "type": "choices",
                            "value": {"choices": ["yes"]},
                        },
                        {
                            "from_name": "needs_rework",
                            "to_name": "image",
                            "type": "choices",
                            "value": {"choices": ["yes"]},
                        },
                    ],
                }
            ],
        }
    ]
    export.write_text(json.dumps(payload), encoding="utf-8")

    code = main(
        [
            "rework-import",
            "--batch",
            batch_id,
            "--task",
            "cap",
            "--export",
            str(export),
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    out_file = (
        data_root / "ls_import" / batch_id / "cap" / "rework_tasks.json"
    )
    assert out_file.is_file()
    assert str(out_file.resolve()) in captured.out or str(out_file) in captured.out
    tasks = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(tasks) == 1
    assert tasks[0]["id"] == image_id


def test_rework_import_missing_export(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "rework-import",
            "--batch",
            "batch_cli",
            "--task",
            "cap",
            "--export",
            str(tmp_path / "missing.json"),
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma rework-import:" in captured.err


def test_export_split_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_root = tmp_path / "data"
    export = tmp_path / "cap_export.json"
    _write_cap_export(export, image_id="img-a", caption="hi")
    code = main(
        [
            "export-split",
            "--batch",
            "batch_cli",
            "--task",
            "cap",
            "--export",
            str(export),
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    normal = (
        data_root / "results" / "batch_cli" / "cap" / "normal" / "annotations.json"
    )
    rework = (
        data_root / "results" / "batch_cli" / "cap" / "rework" / "annotations.json"
    )
    pending = (
        data_root / "results" / "batch_cli" / "cap" / "pending" / "annotations.json"
    )
    assert normal.is_file()
    assert rework.is_file()
    assert not pending.is_file()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 2
    assert str(normal.resolve()) in lines[0] or str(normal) in lines[0]
    assert str(rework.resolve()) in lines[1] or str(rework) in lines[1]
    assert json.loads(normal.read_text(encoding="utf-8"))[0]["image_id"] == "img-a"
    assert json.loads(rework.read_text(encoding="utf-8")) == []


def test_export_split_missing_export(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "export-split",
            "--batch",
            "batch_cli",
            "--task",
            "cap",
            "--export",
            str(tmp_path / "missing.json"),
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma export-split:" in captured.err


def test_preprocess_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    images, excel, data_root = _prepare_preprocess_inputs(tmp_path)
    code = main(
        [
            "preprocess",
            "--batch",
            "batch_cli",
            "--images",
            str(images),
            "--excel",
            str(excel),
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    out_dir = data_root / "processed" / "batch_cli"
    assert str(out_dir) in captured.out
    manifest = out_dir / "manifest.json"
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch_cli"
    assert len(payload["items"]) == 1


def test_preprocess_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    images, excel, data_root = _prepare_preprocess_inputs(tmp_path)
    code = main(
        [
            "preprocess",
            "--batch",
            "bad/id",
            "--images",
            str(images),
            "--excel",
            str(excel),
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma preprocess:" in captured.err
    assert not (data_root / "processed" / "bad").exists()


def test_package_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    images, excel, data_root = _prepare_preprocess_inputs(tmp_path)
    assert (
        main(
            [
                "preprocess",
                "--batch",
                "batch_pkg",
                "--images",
                str(images),
                "--excel",
                str(excel),
                "--data-root",
                str(data_root),
            ]
        )
        == 0
    )
    capsys.readouterr()

    code = main(
        [
            "package",
            "--batch",
            "batch_pkg",
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    out_dir = data_root / "task_packages" / "batch_pkg"
    assert str(out_dir) in captured.out
    for task in ("seg", "det", "cap"):
        manifest = out_dir / task / "manifest.json"
        assert manifest.is_file()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["package_id"] == f"batch_pkg__{task}"
        assert payload["task_type"] == task.upper()


def test_package_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "package",
            "--batch",
            "missing_batch",
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma package:" in captured.err


def _write_merge_ready_fixture(data_root: Path, batch_id: str = "batch_merge") -> None:
    from mma.common.io import write_json
    from mma.common.models import (
        BBox,
        CapAnnotation,
        DetAnnotation,
        SegAnnotation,
        TaskAnnotationResult,
        TaskType,
    )
    from mma.converters.seg_brush import save_binary_mask_png
    from mma.exporters import overwrite_current

    def seg(image_id: str) -> TaskAnnotationResult:
        return TaskAnnotationResult(
            image_id=image_id,
            task_type=TaskType.SEG,
            annotation=SegAnnotation(mask_ref=f"manual_masks/{image_id}_manual.png"),
            human_confirmed=True,
            needs_rework=False,
        )

    def det(image_id: str) -> TaskAnnotationResult:
        return TaskAnnotationResult(
            image_id=image_id,
            task_type=TaskType.DET,
            annotation=DetAnnotation(
                bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
            ),
            human_confirmed=True,
            needs_rework=False,
        )

    def cap(image_id: str) -> TaskAnnotationResult:
        return TaskAnnotationResult(
            image_id=image_id,
            task_type=TaskType.CAP,
            annotation=CapAnnotation(caption=f"cap-{image_id}"),
            human_confirmed=True,
            needs_rework=False,
        )

    image_id = "img-a"
    overwrite_current(
        [seg(image_id)],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=data_root,
    )
    overwrite_current(
        [det(image_id)],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=data_root,
    )
    overwrite_current(
        [cap(image_id)],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=data_root,
    )
    save_binary_mask_png(
        data_root
        / "results"
        / batch_id
        / "seg"
        / "manual_masks"
        / f"{image_id}_manual.png",
        [[0, 1], [1, 0]],
    )
    images_dir = data_root / "raw" / batch_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_file = images_dir / f"{image_id}.jpg"
    image_file.write_bytes(_MIN_JPEG)
    write_json(
        data_root / "processed" / batch_id / "manifest.json",
        {
            "batch_id": batch_id,
            "items": [
                {
                    "image_id": image_id,
                    "image_path": str(image_file.resolve()),
                    "diagnosis_text": f"diag-{image_id}",
                    "source_image_name": image_file.name,
                }
            ],
        },
    )


def test_merge_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_root = tmp_path / "data"
    _write_merge_ready_fixture(data_root)
    code = main(
        [
            "merge",
            "--batch",
            "batch_merge",
            "--data-root",
            str(data_root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    out_file = data_root / "final" / "batch_merge" / "manifest.json"
    assert out_file.is_file()
    assert str(out_file.resolve()) in captured.out or str(out_file) in captured.out
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["items"][0]["image_id"] == "img-a"
    assert payload["items"][0]["cap"]["caption"] == "cap-img-a"
    assert payload["items"][0]["image_path"] == "images/img-a.jpg"
    assert payload["items"][0]["seg"]["mask_ref"] == "masks/img-a.png"
    assert (data_root / "final" / "batch_merge" / "images" / "img-a.jpg").is_file()
    assert (data_root / "final" / "batch_merge" / "masks" / "img-a.png").is_file()


def test_merge_failure_not_ready(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "merge",
            "--batch",
            "missing_batch",
            "--data-root",
            str(tmp_path / "data"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "mma merge:" in captured.err


def test_module_entry_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mma", "-h"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "preprocess" in result.stdout
    assert "merge" in result.stdout
