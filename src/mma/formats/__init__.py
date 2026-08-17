"""Formats namespace: V1 task / annotation schema (re-exports).

Prelabel intermediate types live under ``mma.formats.legacy_prelabel`` and are
**not** re-exported here.
"""

from mma.formats.annotation_schema import (
    AnnotationPayload,
    BBox,
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    ResultBundle,
    SegAnnotation,
    TaskAnnotationResult,
)
from mma.formats.task_schema import (
    BatchContext,
    BundleKind,
    ImageRecord,
    ImageTextPair,
    SampleItem,
    TaskPackage,
    TaskType,
)

__all__ = [
    "AnnotationPayload",
    "BBox",
    "BatchContext",
    "BundleKind",
    "CapAnnotation",
    "DetAnnotation",
    "ImageRecord",
    "ImageTextPair",
    "MergedMultitaskRecord",
    "ResultBundle",
    "SampleItem",
    "SegAnnotation",
    "TaskAnnotationResult",
    "TaskPackage",
    "TaskType",
]
