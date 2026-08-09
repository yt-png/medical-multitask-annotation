"""Tests for unified CLI skeleton (T0.4). No business I/O."""

from __future__ import annotations

import subprocess
import sys

import pytest

from mma.cli import SUBCOMMANDS, TASK_CHOICES, build_parser, main


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
def test_valid_task_accepted_then_stub(task: str, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["convert", "--batch", "b1", "--task", task])
    assert code == 2
    err = capsys.readouterr().err
    assert "not implemented yet" in err
    assert "convert" in err


def test_stub_for_package(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["package", "--batch", "batch-a"])
    assert code == 2
    assert "not implemented yet" in capsys.readouterr().err


def test_stub_for_merge(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["merge", "--batch", "batch-a"])
    assert code == 2
    assert "merge" in capsys.readouterr().err


def test_export_split_requires_export() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["export-split", "--batch", "b1", "--task", "seg"])
    assert exc.value.code == 2


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
