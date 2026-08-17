"""Tests for V1 formats namespace: task_schema / annotation_schema re-exports."""

from __future__ import annotations

import pytest

from mma.common import models as common_models
from mma.formats import (
    AnnotationPayload,
    BBox,
    BatchContext,
    BundleKind,
    CapAnnotation,
    DetAnnotation,
    ImageRecord,
    ImageTextPair,
    MergedMultitaskRecord,
    ResultBundle,
    SampleItem,
    SegAnnotation,
    TaskAnnotationResult,
    TaskPackage,
    TaskType,
)
from mma.formats import annotation_schema, task_schema


def test_formats_package_exports_match_common_models() -> None:
    assert TaskType is common_models.TaskType
    assert BundleKind is common_models.BundleKind
    assert BatchContext is common_models.BatchContext
    assert ImageRecord is common_models.ImageRecord
    assert ImageTextPair is common_models.ImageTextPair
    assert SampleItem is common_models.SampleItem
    assert TaskPackage is common_models.TaskPackage
    assert BBox is common_models.BBox
    assert SegAnnotation is common_models.SegAnnotation
    assert DetAnnotation is common_models.DetAnnotation
    assert CapAnnotation is common_models.CapAnnotation
    assert AnnotationPayload is common_models.AnnotationPayload
    assert TaskAnnotationResult is common_models.TaskAnnotationResult
    assert ResultBundle is common_models.ResultBundle
    assert MergedMultitaskRecord is common_models.MergedMultitaskRecord


def test_subpackage_reexports_align_with_formats_root() -> None:
    assert task_schema.TaskType is TaskType
    assert task_schema.TaskPackage is TaskPackage
    assert annotation_schema.SegAnnotation is SegAnnotation
    assert annotation_schema.TaskAnnotationResult is TaskAnnotationResult


def test_formats_root_does_not_export_prelabel_types() -> None:
    import mma.formats as formats_pkg

    for name in (
        "PrelabelItem",
        "PrelabelDocument",
        "PrelabelPayload",
        "PrelabelBBox",
        "SegPrelabelPayload",
        "load_prelabel_document",
    ):
        assert not hasattr(formats_pkg, name)


def test_task_schema_constructs_minimal_package() -> None:
    package = TaskPackage(
        package_id="demo_batch__seg",
        task_type=TaskType.SEG,
        samples=(
            SampleItem(
                image_id="demo_batch__000001",
                image_path="images/a.jpg",
                diagnosis_text="diag",
            ),
        ),
        batch_id="demo_batch",
    )
    assert package.task_type is TaskType.SEG
    assert len(package.samples) == 1


def test_annotation_schema_constructs_result() -> None:
    result = TaskAnnotationResult(
        image_id="demo_batch__000001",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)),
        human_confirmed=True,
        needs_rework=False,
    )
    assert isinstance(result.annotation, DetAnnotation)
    with pytest.raises(ValueError, match="does not match"):
        TaskAnnotationResult(
            image_id="x",
            task_type=TaskType.SEG,
            annotation=CapAnnotation(caption="nope"),
            human_confirmed=True,
            needs_rework=False,
        )
