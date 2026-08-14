"""Core data contracts for the multitask annotation pipeline.

Prelabel intermediate formats (pixel bbox, mask file refs, etc.) live in
``mma.formats`` — see ``docs/formats.md``. This module defines business-stage
field names, types, and light consistency checks only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union


class TaskType(str, Enum):
    """Annotation task type; SEG / DET / CAP remain independent chains."""

    SEG = "SEG"
    DET = "DET"
    CAP = "CAP"


class BundleKind(str, Enum):
    """Export classification: normal vs rework result bundle."""

    NORMAL = "normal"
    REWORK = "rework"


@dataclass(frozen=True)
class BatchContext:
    """Batch-level identity used across pipeline stages."""

    batch_id: str


@dataclass(frozen=True)
class BBox:
    """Axis-aligned box: x, y, width, height.

    Coordinate space is not fixed here. Prelabel intermediate DET uses
    ``mma.formats.PrelabelBBox`` (pixel coordinates); see ``docs/formats.md``.
    """

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SegAnnotation:
    """SEG annotation payload; mask stored as a string reference.

    Prelabel-stage SEG uses ``mma.formats.SegPrelabelPayload`` (file ref only).
    """

    mask_ref: str


@dataclass(frozen=True)
class DetAnnotation:
    """DET annotation payload (post-confirmation / merge stage)."""

    bboxes: tuple[BBox, ...]


@dataclass(frozen=True)
class CapAnnotation:
    """CAP annotation payload (post-confirmation / merge stage)."""

    caption: str


AnnotationPayload = Union[SegAnnotation, DetAnnotation, CapAnnotation]


@dataclass(frozen=True)
class ImageRecord:
    """Image-level object shared across the pipeline."""

    image_id: str
    image_path: str
    diagnosis_text: str
    batch_id: str | None = None
    source_image_name: str | None = None


@dataclass(frozen=True)
class ImageTextPair:
    """Pre-ID image/text binding from jpg + Excel pairing (T1.1).

    Does not carry image_id; that is assigned in T1.2.
    """

    image_path: str
    diagnosis_text: str
    source_image_name: str
    batch_id: str | None = None


@dataclass(frozen=True)
class SampleItem:
    """Single sample inside a task package."""

    image_id: str
    image_path: str
    diagnosis_text: str


@dataclass(frozen=True)
class TaskPackage:
    """Task package for one task type; empty samples allowed at T0.2."""

    package_id: str
    task_type: TaskType
    samples: tuple[SampleItem, ...]
    batch_id: str | None = None


def assert_annotation_matches_task(
    task_type: TaskType,
    annotation: AnnotationPayload,
) -> None:
    """Ensure annotation payload type matches the task type."""

    expected: type[AnnotationPayload]
    if task_type is TaskType.SEG:
        expected = SegAnnotation
    elif task_type is TaskType.DET:
        expected = DetAnnotation
    elif task_type is TaskType.CAP:
        expected = CapAnnotation
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError(f"unsupported task type: {task_type!r}")

    if not isinstance(annotation, expected):
        raise ValueError(
            f"annotation type {type(annotation).__name__} does not match "
            f"task type {task_type.value}"
        )


def should_rework(*, human_confirmed: bool, needs_rework: bool) -> bool:
    """Return whether a sample belongs in the rework path.

    Business rule::

        should_rework = (not human_confirmed) or needs_rework

    Only ``human_confirmed=True`` and ``needs_rework=False`` is normal.
    """

    return (not human_confirmed) or needs_rework


@dataclass(frozen=True)
class TaskAnnotationResult:
    """Current effective single-task annotation result (overwrite semantics)."""

    image_id: str
    task_type: TaskType
    annotation: AnnotationPayload
    human_confirmed: bool
    needs_rework: bool
    package_id: str | None = None
    export_round: int | None = None

    def __post_init__(self) -> None:
        assert_annotation_matches_task(self.task_type, self.annotation)


def assert_result_bundle_consistent(bundle: ResultBundle) -> None:
    """Validate result bundle kind vs ``should_rework`` and task_type alignment."""

    for item in bundle.items:
        if item.task_type is not bundle.task_type:
            raise ValueError(
                f"item task_type {item.task_type.value} does not match "
                f"bundle task_type {bundle.task_type.value}"
            )
        item_should_rework = should_rework(
            human_confirmed=item.human_confirmed,
            needs_rework=item.needs_rework,
        )
        if bundle.bundle_kind is BundleKind.NORMAL and item_should_rework:
            raise ValueError(
                "NORMAL bundle cannot contain items that should_rework "
                f"(image_id={item.image_id!r}, "
                f"human_confirmed={item.human_confirmed}, "
                f"needs_rework={item.needs_rework})"
            )
        if bundle.bundle_kind is BundleKind.REWORK and not item_should_rework:
            raise ValueError(
                "REWORK bundle cannot contain items that should not rework "
                f"(image_id={item.image_id!r}, "
                f"human_confirmed={item.human_confirmed}, "
                f"needs_rework={item.needs_rework})"
            )


@dataclass(frozen=True)
class ResultBundle:
    """Classified export bundle: normal or rework."""

    bundle_kind: BundleKind
    task_type: TaskType
    items: tuple[TaskAnnotationResult, ...]
    batch_id: str | None = None

    def __post_init__(self) -> None:
        assert_result_bundle_consistent(self)


@dataclass(frozen=True)
class MergedMultitaskRecord:
    """Final multitask record: one image with SEG + DET + CAP."""

    image_id: str
    seg: SegAnnotation
    det: DetAnnotation
    cap: CapAnnotation
    image_path: str | None = None
    diagnosis_text: str | None = None
