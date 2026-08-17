"""Legacy tests for prelabel adapters (T2.3): Base constraints + Example adapters.

Not part of the V1 runtime test suite; run with ``pytest -m legacy``.
"""

from __future__ import annotations

import pytest

from mma.common.models import TaskType
from mma.converters import ImageMetadata, item_to_ls_task
from mma.formats.legacy_prelabel import (
    CapPrelabelPayload,
    DetPrelabelPayload,
    SCHEMA_VERSION,
    SegPrelabelPayload,
)
from mma.legacy.adapters import (
    AdapterContext,
    CapPrelabelAdapter,
    DetPrelabelAdapter,
    ExampleCapAdapter,
    ExampleDetAdapter,
    ExampleSegAdapter,
    SegPrelabelAdapter,
)

pytestmark = pytest.mark.legacy


def _seg_context(**overrides: object) -> AdapterContext:
    data: dict[str, object] = {
        "batch_id": "demo_batch",
        "package_id": "demo_batch__seg",
        "task_type": TaskType.SEG,
        "image_id": "demo_batch__000001",
        "diagnosis_text": "original diagnosis",
        "schema_version": SCHEMA_VERSION,
        "image_path": "optional/a.jpg",
    }
    data.update(overrides)
    return AdapterContext(**data)  # type: ignore[arg-type]


def _det_context(**overrides: object) -> AdapterContext:
    return _seg_context(
        package_id="demo_batch__det",
        task_type=TaskType.DET,
        **overrides,
    )


def _cap_context(**overrides: object) -> AdapterContext:
    return _seg_context(
        package_id="demo_batch__cap",
        task_type=TaskType.CAP,
        **overrides,
    )


@pytest.mark.parametrize(
    ("adapter_cls", "context_factory"),
    [
        (SegPrelabelAdapter, _seg_context),
        (DetPrelabelAdapter, _det_context),
        (CapPrelabelAdapter, _cap_context),
    ],
)
def test_base_adapt_payload_raises_not_implemented(
    adapter_cls: type,
    context_factory: object,
) -> None:
    adapter = adapter_cls()
    context = context_factory()  # type: ignore[operator]
    with pytest.raises(NotImplementedError, match="not implemented"):
        adapter.adapt_payload({}, context=context)


def test_example_seg_adapt_item() -> None:
    context = _seg_context()
    item = ExampleSegAdapter().adapt_item(
        {"mask_ref": "masks/demo_batch__000001.png"},
        context=context,
    )
    assert isinstance(item.payload, SegPrelabelPayload)
    assert item.payload.mask_ref == "masks/demo_batch__000001.png"
    assert item.image_id == context.image_id
    assert item.batch_id == context.batch_id
    assert item.package_id == context.package_id
    assert item.diagnosis_text == context.diagnosis_text
    assert item.image_path == context.image_path
    assert item.task_type is TaskType.SEG


def test_example_det_multi_and_empty_bboxes() -> None:
    adapter = ExampleDetAdapter()
    multi = adapter.adapt_payload(
        {
            "bboxes": [
                {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
                {"x": 10.0, "y": 20.0, "width": 5.0, "height": 6.0},
            ]
        },
        context=_det_context(),
    )
    assert isinstance(multi, DetPrelabelPayload)
    assert len(multi.bboxes) == 2
    assert multi.bboxes[0].x == 1.0

    empty = adapter.adapt_payload({"bboxes": []}, context=_det_context())
    assert empty.bboxes == ()


def test_example_cap_keeps_diagnosis_from_context() -> None:
    context = _cap_context(diagnosis_text="excel original text")
    item = ExampleCapAdapter().adapt_item(
        {"caption": "model generated caption"},
        context=context,
    )
    assert isinstance(item.payload, CapPrelabelPayload)
    assert item.payload.caption == "model generated caption"
    assert item.diagnosis_text == "excel original text"
    assert item.payload.caption != item.diagnosis_text


def test_example_seg_missing_mask_ref() -> None:
    with pytest.raises(ValueError, match="mask_ref"):
        ExampleSegAdapter().adapt_payload({}, context=_seg_context())


def test_example_det_missing_bboxes() -> None:
    with pytest.raises(ValueError, match="bboxes"):
        ExampleDetAdapter().adapt_payload({}, context=_det_context())


def test_adapt_item_rejects_mismatched_task_type() -> None:
    with pytest.raises(ValueError, match="task_type=SEG"):
        ExampleSegAdapter().adapt_item(
            {"mask_ref": "masks/a.png"},
            context=_det_context(),
        )


def test_example_seg_to_ls_task_pipeline() -> None:
    item = ExampleSegAdapter().adapt_item(
        {"mask_ref": "masks/a.png"},
        context=_seg_context(image_path=None),
    )
    task = item_to_ls_task(item)
    assert task["data"]["mask_ref"] == "masks/a.png"
    assert task["predictions"][0]["result"] == []


def test_example_det_to_ls_task_pipeline() -> None:
    item = ExampleDetAdapter().adapt_item(
        {"bboxes": [{"x": 64.0, "y": 48.0, "width": 32.0, "height": 16.0}]},
        context=_det_context(),
    )
    task = item_to_ls_task(item, image_metadata=ImageMetadata(width=640, height=480))
    result = task["predictions"][0]["result"][0]
    assert result["value"]["x"] == pytest.approx(10.0)
    assert result["value"]["y"] == pytest.approx(10.0)
