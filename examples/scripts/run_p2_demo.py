#!/usr/bin/env python3
"""P2 demo: fake algorithm raw → Example adapter → LS import JSON.

Demonstration only. Not a pipeline framework and not part of ``src/mma``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mma.adapters import (
    AdapterContext,
    ExampleCapAdapter,
    ExampleDetAdapter,
    ExampleSegAdapter,
)
from mma.common.io import write_json
from mma.common.models import TaskType
from mma.converters import ImageMetadata, document_to_ls_tasks
from mma.formats import PrelabelDocument, PrelabelItem, SCHEMA_VERSION

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEMO_DIR = _REPO_ROOT / "examples" / "adapter_raw" / "demo_batch"

_TASK_DIR = {
    TaskType.SEG: "seg",
    TaskType.DET: "det",
    TaskType.CAP: "cap",
}

_EXAMPLE_ADAPTERS = {
    TaskType.SEG: ExampleSegAdapter,
    TaskType.DET: ExampleDetAdapter,
    TaskType.CAP: ExampleCapAdapter,
}

# Demo-only image size for DET percent conversion.
_DEMO_IMAGE_SIZE = ImageMetadata(width=640, height=480)


def load_raw_entries(path: Path | str) -> list[dict[str, Any]]:
    """Load fake algorithm raw file. Only ``{\"items\": [...]}`` is supported."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"raw file must be an object: {path}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError(f"raw file must contain an items list: {path}")
    if not items:
        raise ValueError(f"raw file items must not be empty: {path}")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"raw items[{index}] must be an object: {path}")
    return items


def load_demo_contexts(path: Path | str) -> tuple[str, str, list[dict[str, Any]]]:
    """Load caller-side envelope rows (not algorithm raw)."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"contexts file must be an object: {path}")
    batch_id = payload.get("batch_id")
    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    items = payload.get("items")
    if not isinstance(batch_id, str) or not batch_id.strip():
        raise ValueError(f"contexts.batch_id must be a non-empty string: {path}")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError(f"contexts.schema_version must be a non-empty string: {path}")
    if not isinstance(items, list) or not items:
        raise ValueError(f"contexts.items must be a non-empty list: {path}")
    return batch_id.strip(), schema_version.strip(), items


def build_context(
    *,
    batch_id: str,
    schema_version: str,
    task_type: TaskType,
    envelope: dict[str, Any],
) -> AdapterContext:
    """Inject business envelope into ``AdapterContext`` (not from algorithm raw)."""

    image_id = envelope.get("image_id")
    diagnosis_text = envelope.get("diagnosis_text")
    if not isinstance(image_id, str) or not image_id.strip():
        raise ValueError("context item image_id must be a non-empty string")
    if not isinstance(diagnosis_text, str) or not diagnosis_text.strip():
        raise ValueError(
            f"context item diagnosis_text must be a non-empty string "
            f"(image_id={image_id!r})"
        )
    image_path = envelope.get("image_path")
    if image_path is not None and (
        not isinstance(image_path, str) or not image_path.strip()
    ):
        raise ValueError(
            f"context item image_path must be null or non-empty string "
            f"(image_id={image_id!r})"
        )
    task_dir = _TASK_DIR[task_type]
    return AdapterContext(
        schema_version=schema_version,
        batch_id=batch_id,
        package_id=f"{batch_id}__{task_dir}",
        task_type=task_type,
        image_id=image_id.strip(),
        diagnosis_text=diagnosis_text.strip(),
        image_path=image_path,
    )


def adapt_task(
    task_type: TaskType,
    raw_entries: list[dict[str, Any]],
    *,
    batch_id: str,
    schema_version: str,
    envelopes: list[dict[str, Any]],
) -> PrelabelDocument:
    """Run Example adapter for one task and assemble a ``PrelabelDocument``."""

    if len(raw_entries) != len(envelopes):
        raise ValueError(
            f"{task_type.value}: raw items ({len(raw_entries)}) and "
            f"context items ({len(envelopes)}) length mismatch"
        )

    adapter = _EXAMPLE_ADAPTERS[task_type]()
    items: list[PrelabelItem] = []
    for raw, envelope in zip(raw_entries, envelopes, strict=True):
        context = build_context(
            batch_id=batch_id,
            schema_version=schema_version,
            task_type=task_type,
            envelope=envelope,
        )
        items.append(adapter.adapt_item(raw, context=context))

    package_id = f"{batch_id}__{_TASK_DIR[task_type]}"
    return PrelabelDocument(
        schema_version=schema_version,
        batch_id=batch_id,
        package_id=package_id,
        task_type=task_type,
        items=tuple(items),
    )


def convert_task(
    document: PrelabelDocument,
    *,
    image_metadata: ImageMetadata = _DEMO_IMAGE_SIZE,
) -> list[dict[str, Any]]:
    """Convert a prelabel document to Label Studio import tasks."""

    if document.task_type is TaskType.DET:
        meta_by_id = {
            item.image_id: image_metadata for item in document.items
        }
        return document_to_ls_tasks(
            document, image_metadata_by_id=meta_by_id
        )
    return document_to_ls_tasks(document)


def run_demo(*, out_dir: Path | None = None) -> dict[TaskType, list[dict[str, Any]]]:
    """Execute the three-task demo pipeline once."""

    batch_id, schema_version, envelopes = load_demo_contexts(
        _DEMO_DIR / "contexts.json"
    )
    results: dict[TaskType, list[dict[str, Any]]] = {}

    for task_type in (TaskType.SEG, TaskType.DET, TaskType.CAP):
        raw_name = f"{_TASK_DIR[task_type]}_raw.json"
        raw_entries = load_raw_entries(_DEMO_DIR / raw_name)
        document = adapt_task(
            task_type,
            raw_entries,
            batch_id=batch_id,
            schema_version=schema_version,
            envelopes=envelopes,
        )
        tasks = convert_task(document)
        results[task_type] = tasks
        print(
            f"{task_type.value}: {len(tasks)} LS tasks; "
            f"image_ids={[t['data']['image_id'] for t in tasks]}"
        )
        if out_dir is not None:
            target = out_dir / _TASK_DIR[task_type] / "tasks.json"
            write_json(target, tasks)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Demo: examples/adapter_raw → Example adapters → "
            "Label Studio import JSON (P2)."
        )
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Optional directory to write {seg,det,cap}/tasks.json",
    )
    args = parser.parse_args(argv)
    run_demo(out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
