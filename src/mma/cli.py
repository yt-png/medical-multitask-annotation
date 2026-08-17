"""Unified CLI entry for the multitask annotation pipeline.

V1 main flow: ``preprocess``, ``package``, ``ls-import`` (empty tasks from
task_packages), ``export-split``, ``rework-import``, ``apply-current``,
``merge``. ``convert`` is a **LEGACY** stub (not part of the V1 main workflow).
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


def _run_convert_legacy_stub(_args: argparse.Namespace) -> int:
    """LEGACY convert entry: not wired; point users at V1 ``ls-import``."""

    print(
        "mma convert: LEGACY only — V1 does not support prelabel conversion.\n"
        "This command is a legacy stub and does not run any conversion.\n"
        "Use `mma ls-import` to build empty Label Studio tasks from "
        "task_packages (V1 recommended path).\n"
        "(Python API mma.converters.document_to_ls_tasks remains available "
        "for legacy/tests only.)",
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
        help=(
            "LEGACY only: V1 does not support prelabel conversion "
            "(stub; use ls-import)."
        ),
        description=(
            "LEGACY only. V1 does not support prelabel conversion. "
            "This command is a stub and performs no conversion. "
            "Use `mma ls-import` to build empty Label Studio tasks from "
            "task_packages."
        ),
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
        help=(
            "Build empty Label Studio annotation tasks from task_packages "
            "(V1 manual workflow; no predictions)."
        ),
        description=(
            "V1 first-round import: read task_packages only and write empty "
            "LS tasks (data fields only; no predictions / prelabels)."
        ),
    )
    ls_import.add_argument("--batch", required=True, help="Batch ID")
    ls_import.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )
    ls_import.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )
    ls_import.add_argument(
        "--local-root",
        default=None,
        help=(
            "Label Studio local storage root for /data/local-files/?d= paths "
            "(default: same as --data-root)"
        ),
    )

    export_split = subparsers.add_parser(
        "export-split",
        help=(
            "High-level: apply-current + return normal/rework paths (P4). "
            "Do not also run apply-current on the same export."
        ),
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
    export_split.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )

    rework_import = subparsers.add_parser(
        "rework-import",
        help=(
            "Build rework import tasks from previous_annotations "
            "(V1 human-history prefill; does not read prelabels). "
            "--export only for legacy packs."
        ),
    )
    rework_import.add_argument("--batch", required=True, help="Batch ID")
    rework_import.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )
    rework_import.add_argument(
        "--export",
        default=None,
        help=(
            "Optional Label Studio export JSON (legacy packs only). "
            "Not used when rework/previous_annotations/<task>.json exists. "
            "Does not read prelabels."
        ),
    )
    rework_import.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )
    rework_import.add_argument(
        "--local-root",
        default=None,
        help=(
            "Label Studio local storage root for /data/local-files/?d= paths "
            "(default: same as --data-root)"
        ),
    )

    apply_current = subparsers.add_parser(
        "apply-current",
        help=(
            "Low-level: export → merge current/ (also refreshes normal/rework) (P4). "
            "Prefer export-split when you need classified bundles."
        ),
    )
    apply_current.add_argument("--batch", required=True, help="Batch ID")
    apply_current.add_argument(
        "--task",
        required=True,
        choices=TASK_CHOICES,
        help="Task type subdirectory",
    )
    apply_current.add_argument(
        "--export",
        required=True,
        help="Path to Label Studio export JSON",
    )
    apply_current.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )

    merge = subparsers.add_parser(
        "merge",
        help="Merge SEG/DET/CAP current results into final dataset (P5).",
    )
    merge.add_argument("--batch", required=True, help="Batch ID")
    merge.add_argument(
        "--data-root",
        default=None,
        help="Runtime data root (default: ./data)",
    )

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


def _run_ls_import(args: argparse.Namespace) -> int:
    from mma.importers.build_ls_tasks import build_ls_import_tasks

    try:
        out_path = build_ls_import_tasks(
            args.batch,
            args.task,
            data_root=args.data_root,
            local_root=args.local_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma ls-import: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_path)))
    return 0


def _run_apply_current(args: argparse.Namespace) -> int:
    from mma.exporters.apply_current_from_export import apply_current_from_export

    try:
        out_path = apply_current_from_export(
            args.export,
            batch_id=args.batch,
            task=args.task,
            data_root=args.data_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma apply-current: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_path)))
    return 0


def _run_export_split(args: argparse.Namespace) -> int:
    from mma.exporters.export_split_from_export import export_split_from_export

    try:
        normal_path, rework_path = export_split_from_export(
            args.export,
            batch_id=args.batch,
            task=args.task,
            data_root=args.data_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma export-split: {exc}", file=sys.stderr)
        return 2

    print(str(Path(normal_path)))
    print(str(Path(rework_path)))
    return 0


def _run_rework_import(args: argparse.Namespace) -> int:
    from mma.importers.rework_import_from_export import rework_import_from_export

    try:
        out_path = rework_import_from_export(
            args.export,
            batch_id=args.batch,
            task=args.task,
            data_root=args.data_root,
            local_root=args.local_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma rework-import: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_path)))
    return 0


def _run_merge(args: argparse.Namespace) -> int:
    from mma.merge.merge_to_final import merge_to_final

    try:
        out_path = merge_to_final(
            args.batch,
            data_root=args.data_root,
        )
    except (OSError, ValueError) as exc:
        print(f"mma merge: {exc}", file=sys.stderr)
        return 2

    print(str(Path(out_path)))
    return 0


def dispatch(args: argparse.Namespace) -> int:
    """Route parsed args to handlers."""

    command = args.command
    if command == "preprocess":
        return _run_preprocess(args)
    if command == "package":
        return _run_package(args)
    if command == "convert":
        return _run_convert_legacy_stub(args)
    if command == "ls-import":
        return _run_ls_import(args)
    if command == "apply-current":
        return _run_apply_current(args)
    if command == "export-split":
        return _run_export_split(args)
    if command == "rework-import":
        return _run_rework_import(args)
    if command == "merge":
        return _run_merge(args)
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
