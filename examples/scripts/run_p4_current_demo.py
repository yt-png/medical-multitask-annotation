#!/usr/bin/env python3
"""P4 demo: LS export JSON → parse → overwrite current annotations.

Demonstration only. Not a pipeline framework and not part of ``src/mma``.
Uses existing ``data/ls_export/demo_batch/{seg,det,cap}/*.json`` fake exports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from mma.common.models import TaskType
from mma.common.paths import task_package_dir
from mma.converters import ImageMetadata
from mma.exporters import overwrite_current, parse_ls_export, split_by_rework
from mma.importers.build_ls_tasks import resolve_task_image_path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "data"
_BATCH_ID = "demo_batch"

_TASK_DIR = {
    TaskType.SEG: "seg",
    TaskType.DET: "det",
    TaskType.CAP: "cap",
}

# Exact demo export filenames under data/ls_export/demo_batch/.
_EXPORT_FILENAMES = {
    TaskType.SEG: "project-14-at-2026-08-11-10-30-fda1a4bc.json",
    TaskType.DET: "project-15-at-2026-08-11-10-31-dada240b.json",
    TaskType.CAP: "project-16-at-2026-08-11-10-33-a94520f3.json",
}


def resolve_export_json(
    data_root: Path,
    task_type: TaskType,
) -> Path:
    """Resolve the demo Label Studio export JSON for one task."""

    task_key = _TASK_DIR[task_type]
    path = (
        data_root
        / "ls_export"
        / _BATCH_ID
        / task_key
        / _EXPORT_FILENAMES[task_type]
    )
    if not path.is_file():
        raise FileNotFoundError(
            f"LS export not found for {task_type.value}: {path}"
        )
    return path


def det_image_metadata_by_id(
    data_root: Path,
    image_ids: list[str],
) -> dict[str, ImageMetadata]:
    """Build DET pixel conversion metadata from task-package images."""

    meta: dict[str, ImageMetadata] = {}
    for image_id in image_ids:
        image_path = resolve_task_image_path(
            _BATCH_ID,
            "det",
            image_id,
            data_root=data_root,
        )
        with Image.open(image_path) as img:
            width, height = img.size
        meta[image_id] = ImageMetadata(width=width, height=height)
    return meta


def peek_export_image_ids(export_path: Path) -> list[str]:
    """Read image_id list from an export without full T4.1 parsing."""

    from mma.common.io import read_json

    payload = read_json(export_path)
    if not isinstance(payload, list):
        raise ValueError(f"export must be a JSON array: {export_path}")
    image_ids: list[str] = []
    for index, task in enumerate(payload):
        if not isinstance(task, dict):
            raise ValueError(f"export task at index {index} must be an object")
        data = task.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"export task at index {index} missing data object")
        image_id = data.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError(
                f"export task at index {index} missing data.image_id"
            )
        image_ids.append(image_id.strip())
    return image_ids


def run_demo(*, data_root: Path | None = None) -> dict[TaskType, Path]:
    """Parse demo LS exports and overwrite ``current/annotations.json``."""

    root = _DEFAULT_DATA_ROOT if data_root is None else Path(data_root)
    if not root.is_dir():
        raise FileNotFoundError(f"data root not found: {root}")

    # Ensure DET package images exist when we need metadata.
    det_pkg = task_package_dir(_BATCH_ID, "det", data_root=root)
    if not (det_pkg / "images").is_dir():
        raise FileNotFoundError(
            f"DET task package images missing for demo metadata: "
            f"{det_pkg / 'images'}"
        )

    written: dict[TaskType, Path] = {}
    for task_type in (TaskType.SEG, TaskType.DET, TaskType.CAP):
        export_path = resolve_export_json(root, task_type)
        if task_type is TaskType.DET:
            image_ids = peek_export_image_ids(export_path)
            meta = det_image_metadata_by_id(root, image_ids)
            results = parse_ls_export(
                export_path,
                task_type=task_type,
                image_metadata_by_id=meta,
            )
        else:
            results = parse_ls_export(export_path, task_type=task_type)

        normal, rework = split_by_rework(results)
        out_path = overwrite_current(
            results,
            batch_id=_BATCH_ID,
            task_type=task_type,
            data_root=root,
        )
        written[task_type] = out_path

        print(
            f"{task_type.value}: parsed={len(results)} "
            f"normal={len(normal)} rework={len(rework)}"
        )
        print(f"  export={export_path}")
        print(f"  current={out_path}")

    print("done.")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Demo: data/ls_export/demo_batch → parse_ls_export → "
            "overwrite_current → results/.../current/annotations.json"
        )
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Runtime data root (default: <repo>/data)",
    )
    args = parser.parse_args(argv)
    run_demo(data_root=args.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
