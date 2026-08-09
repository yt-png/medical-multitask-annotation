"""Shared primitives: data contracts and utilities."""

from mma.common.models import (
    AnnotationPayload,
    BatchContext,
    BBox,
    BundleKind,
    CapAnnotation,
    DetAnnotation,
    ImageRecord,
    MergedMultitaskRecord,
    ResultBundle,
    SampleItem,
    SegAnnotation,
    TaskAnnotationResult,
    TaskPackage,
    TaskType,
    assert_annotation_matches_task,
    assert_result_bundle_consistent,
)

__all__ = [
    "AnnotationPayload",
    "BatchContext",
    "BBox",
    "BundleKind",
    "CapAnnotation",
    "DetAnnotation",
    "ImageRecord",
    "MergedMultitaskRecord",
    "ResultBundle",
    "SampleItem",
    "SegAnnotation",
    "TaskAnnotationResult",
    "TaskPackage",
    "TaskType",
    "assert_annotation_matches_task",
    "assert_result_bundle_consistent",
]
