"""V1 annotation-stage schema re-exports from ``mma.common.models``.

Canonical definitions remain in ``common.models``; this package is the formats
namespace entry for human / gold-standard annotation types.
"""

from mma.common.models import (
    AnnotationPayload,
    BBox,
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    ResultBundle,
    SegAnnotation,
    TaskAnnotationResult,
)

__all__ = [
    "AnnotationPayload",
    "BBox",
    "CapAnnotation",
    "DetAnnotation",
    "MergedMultitaskRecord",
    "ResultBundle",
    "SegAnnotation",
    "TaskAnnotationResult",
]
