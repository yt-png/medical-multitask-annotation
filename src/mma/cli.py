"""Unified CLI entry for the multitask annotation pipeline.

``preprocess`` and ``package`` are wired; other subcommands remain stubs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

TASK_CHOICES = ("seg", "det", "cap")

SUBCOMMANDS = (
    "preprocess",
    "package",
    "convert",
    "ls-import",
    "export-split",
    "rework-import",
    "apply-current",
    "merge",
)


def _stub(command: str) -> int:
    """Report that the business handler is not implemented yet."""

    print(
        f"mma {command}: not implemented yet "
        "(CLI skeleton only; business logic comes in later stages).",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mma",
        description=(
            "Medical multitask annotation dataflow CLI. "
            "See docs/data_layout.md for batch directory conventions."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preprocess = subparsers.add_parser(
        "preprocess",
        help="Build processed batch index and image-text bindings (P1).",
    )
    preprocess.add_argument("--batch", required=True, help="Batch ID")
    preprocess.add_argument(
        "--images",
        required=True,
        help="Directory containing source JPG images",
    )
    preprocess.add_argument(
        "--excel",
        required=True,
        help="Excel file with diagnosis text",
    )
    preprocess.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )

    package = subparsers.add_parser(
        "package",
        help="Split processed batch into SEG/DET/CAP task packages (P1).",
    )
    package.add_argument("--batch", required=True, help="Batch ID")
    package.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )

    convert = subparsers.add_parser(
        "convert",
        help="Convert prelabels to Label Studio import format (P2).",
    )
    convert.add_argument("--batch", required=True, help="Batch ID")
    convert.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )

    ls_import = subparsers.add_parser(
        "ls-import",
        help="Build Label Studio import tasks (P3).",
    )
    ls_import.add_argument("--batch", required=True, help="Batch ID")
    ls_import.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )

    export_split = subparsers.add_parser(
        "export-split",
        help="Parse LS export and split normal/rework bundles (P4).",
    )
    export_split.add_argument("--batch", required=True, help="Batch ID")
    export_split.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )
    export_split.add_argument(
        "--export",
        required=True,
        help="Path to Label Studio export JSON",
    )

    rework_import = subparsers.add_parser(
        "rework-import",
        help="Build rework import tasks with previous results (P4).",
    )
    rework_import.add_argument("--batch", required=True, help="Batch ID")
    rework_import.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )

    apply_current = subparsers.add_parser(
        "apply-current",
        help="Overwrite current/ with latest effective results (P4).",
    )
    apply_current.add_argument("--batch", required=True, help="Batch ID")
    apply_current.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )

    merge = subparsers.add_parser(
        "merge",
        help="Merge SEG/DET/CAP current results into final dataset (P5).",
    )
    merge.add_argument("--batch", required=True, help="Batch ID")

    return parser


def _run_preprocess(args: argparse.Namespace) -> int:
    from mma.preprocess.build_processed import build_processed_batch

    try:
        out_dir = build_processed_batch(
            args.batch,
            args.images,
            args.excel,
            data_root=args.data_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma preprocess: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_dir)))
    return 0


def _run_package(args: argparse.Namespace) -> int:
    from mma.common.paths import task_packages_batch_dir
    from mma.packaging.build_task_packages import build_task_packages

    try:
        build_task_packages(args.batch, data_root=args.data_root)
        out_dir = task_packages_batch_dir(args.batch, data_root=args.data_root)
    except (OSError, ValueError) as exc:
        print(f"mma package: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_dir)))
    return 0


def dispatch(args: argparse.Namespace) -> int:
    """Route parsed args to handlers."""

    command = args.command
    if command == "preprocess":
        return _run_preprocess(args)
    if command == "package":
        return _run_package(args)
    if command in SUBCOMMANDS:
        return _stub(command)
    print(f"mma: unknown command {command!r}", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch(args)


if __name__ == "__main__":
    raise SystemExit(main())
