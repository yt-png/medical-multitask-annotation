"""End-to-end P2 pipeline test: raw → ExampleAdapter → Document → LS converter.

Legacy integration path (depends on ``mma.legacy.adapters``). Run with
``pytest -m legacy``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mma.common.models import TaskType
from mma.converters import (
    DATA_KEY_DIAGNOSIS_TEXT,
    DATA_KEY_IMAGE_ID,
    DATA_KEY_MASK_REF,
    ImageMetadata,
    document_to_ls_tasks,
)
from mma.formats.legacy_prelabel import (
    CapPrelabelPayload,
    PrelabelDocument,
    SCHEMA_VERSION,
    SegPrelabelPayload,
)
from mma.legacy.adapters import (
    AdapterContext,
    ExampleCapAdapter,
    ExampleDetAdapter,
    ExampleSegAdapter,
)

pytestmark = pytest.mark.legacy

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_DIR = _REPO_ROOT / "examples" / "adapter_raw" / "demo_batch"


def _load_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    items = payload["items"]
    assert isinstance(items, list) and items
    return items


def _build_document(
    task_type: TaskType,
    *,
    raw_name: str,
    adapter: object,
    package_suffix: str,
) -> PrelabelDocument:
    contexts = json.loads((_DEMO_DIR / "contexts.json").read_text(encoding="utf-8"))
    envelopes = contexts["items"]
    raw_entries = _load_items(_DEMO_DIR / raw_name)
    assert len(raw_entries) == len(envelopes)

    batch_id = contexts["batch_id"]
    schema_version = contexts.get("schema_version", SCHEMA_VERSION)
    items = []
    for raw, envelope in zip(raw_entries, envelopes, strict=True):
        context = AdapterContext(
            schema_version=schema_version,
            batch_id=batch_id,
            package_id=f"{batch_id}__{package_suffix}",
            task_type=task_type,
            image_id=envelope["image_id"],
            diagnosis_text=envelope["diagnosis_text"],
            image_path=envelope.get("image_path"),
        )
        items.append(adapter.adapt_item(raw, context=context))  # type: ignore[attr-defined]

    return PrelabelDocument(
        schema_version=schema_version,
        batch_id=batch_id,
        package_id=f"{batch_id}__{package_suffix}",
        task_type=task_type,
        items=tuple(items),
    )


def test_p2_pipeline_adapter_to_ls_for_three_tasks() -> None:
    seg_doc = _build_document(
        TaskType.SEG,
        raw_name="seg_raw.json",
        adapter=ExampleSegAdapter(),
        package_suffix="seg",
    )
    det_doc = _build_document(
        TaskType.DET,
        raw_name="det_raw.json",
        adapter=ExampleDetAdapter(),
        package_suffix="det",
    )
    cap_doc = _build_document(
        TaskType.CAP,
        raw_name="cap_raw.json",
        adapter=ExampleCapAdapter(),
        package_suffix="cap",
    )

    seg_tasks = document_to_ls_tasks(seg_doc)
    assert len(seg_tasks) == 2
    assert isinstance(seg_doc.items[0].payload, SegPrelabelPayload)
    assert seg_tasks[0]["data"][DATA_KEY_MASK_REF] == "masks/demo_batch__000001.png"
    assert seg_tasks[0]["data"][DATA_KEY_IMAGE_ID] == "demo_batch__000001"
    assert seg_tasks[0]["predictions"][0]["result"] == []

    meta = {
        item.image_id: ImageMetadata(width=640, height=480)
        for item in det_doc.items
    }
    det_tasks = document_to_ls_tasks(det_doc, image_metadata_by_id=meta)
    assert len(det_tasks[0]["predictions"][0]["result"]) == 2
    assert det_tasks[1]["predictions"][0]["result"] == []
    first_box = det_tasks[0]["predictions"][0]["result"][0]["value"]
    assert first_box["x"] == pytest.approx(120.0 / 640.0 * 100.0)

    cap_tasks = document_to_ls_tasks(cap_doc)
    assert isinstance(cap_doc.items[0].payload, CapPrelabelPayload)
    assert (
        cap_tasks[0]["data"][DATA_KEY_DIAGNOSIS_TEXT]
        == "right lung nodule, benign appearance"
    )
    assert cap_tasks[0]["predictions"][0]["result"][0]["value"]["text"] == [
        "A small nodule is visible in the right lung field."
    ]
    assert (
        cap_tasks[0]["data"][DATA_KEY_DIAGNOSIS_TEXT]
        != cap_tasks[0]["predictions"][0]["result"][0]["value"]["text"][0]
    )
