"""V1 core data contracts for the multitask annotation pipeline.

``BBox``, ``*Annotation``, ``TaskAnnotationResult``, and related types here are
the V1 annotation schema (also re-exported via ``mma.formats.annotation_schema`` /
``task_schema``). Legacy prelabel intermediate types
(``PrelabelBBox``, ``PrelabelItem``, …) live only under
``mma.formats.legacy_prelabel`` — see ``docs/formats.md``.
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
    """V1 annotation-schema axis-aligned box: x, y, width, height.

    Coordinate space is not fixed on this type. For the legacy prelabel DET
    pixel box, see ``mma.formats.legacy_prelabel.PrelabelBBox`` /
    ``docs/formats.md`` (historical; not the V1 gold-standard model).
    """

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SegAnnotation:
    """V1 SEG annotation payload; mask stored as a string reference.

    This type is a data container only. It does not inspect ``mask_ref`` or
    JSON to decide ``has_foreground``. Runtime writers must pass the result
    of ``compute_has_foreground`` (mask pixels). The dataclass default is
    not a payload judgment.
    """

    mask_ref: str
    has_foreground: bool = True


@dataclass(frozen=True)
class DetAnnotation:
    """V1 DET annotation payload (current / merge stage)."""

    bboxes: tuple[BBox, ...]


@dataclass(frozen=True)
class CapAnnotation:
    """V1 CAP annotation payload (current / merge stage)."""

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
    """Return whether a sample belongs in the rework path (choice flags only).

    Business rule::

        should_rework = (not human_confirmed) or needs_rework

    Only ``human_confirmed=True`` and ``needs_rework=False`` is normal under
    this choice-flag helper. Runtime classification uses ``should_rework_result``
    (also empty / missing task payload → rework).
    """

    return (not human_confirmed) or needs_rework


def has_effective_task_payload(
    task_type: TaskType,
    annotation: AnnotationPayload,
) -> bool:
    """Return whether ``annotation`` carries an effective human task payload.

    Maps the requirement "empty LS result / missing mask·bbox·text" onto the
    already-parsed ``TaskAnnotationResult.annotation`` model:

    - DET: at least one bbox
    - CAP: non-empty caption after strip
    - SEG: non-empty ``mask_ref`` and stored ``has_foreground`` (that flag
      must come from mask pixels via ``compute_has_foreground``)

    ``task_type`` must match ``annotation`` (same as ``assert_annotation_matches_task``).
    """

    assert_annotation_matches_task(task_type, annotation)
    if task_type is TaskType.DET:
        assert isinstance(annotation, DetAnnotation)
        return len(annotation.bboxes) > 0
    if task_type is TaskType.CAP:
        assert isinstance(annotation, CapAnnotation)
        return bool(annotation.caption.strip())
    if task_type is TaskType.SEG:
        assert isinstance(annotation, SegAnnotation)
        return bool(annotation.mask_ref.strip()) and annotation.has_foreground
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover


def should_rework_result(
    item: TaskAnnotationResult,
    *,
    has_task_payload: bool | None = None,
) -> bool:
    """V1 rework rule including empty / missing task payload.

    Business rule::

        should_rework_result =
            (not human_confirmed)
            or needs_rework
            or (not effective_payload)

    ``effective_payload`` is ``has_task_payload`` when provided (non-None),
    otherwise ``has_effective_task_payload(item.task_type, item.annotation)``.
    Callers may pass an overridden payload verdict via ``has_task_payload``.
    """

    if has_task_payload is None:
        effective_payload = has_effective_task_payload(
            item.task_type, item.annotation
        )
    else:
        effective_payload = has_task_payload
    return (
        (not item.human_confirmed)
        or item.needs_rework
        or (not effective_payload)
    )


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
    """Validate result bundle kind vs ``should_rework_result`` and task types."""

    for item in bundle.items:
        if item.task_type is not bundle.task_type:
            raise ValueError(
                f"item task_type {item.task_type.value} does not match "
                f"bundle task_type {bundle.task_type.value}"
            )
        item_should_rework = should_rework_result(item)
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
