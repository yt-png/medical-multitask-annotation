"""Label Studio conversion helpers (legacy prelabel + rework geometry).

Roles:

- **Legacy prelabel conversion**: ``PrelabelDocument`` / ``PrelabelItem`` → LS
  import JSON (including a ``predictions`` key). Historical / reference;
  **not** used by V1 first-round ``mma ls-import`` (empty tasks come from
  ``importers.build_ls_tasks``).
- **Rework prefill**: geometry builders may encode **previous human** masks /
  boxes / text for rework import display.

**Semantics**: Label Studio field name ``predictions`` ≠ model inference
output. In rework / ``previous_annotations`` usage it is historical human
annotation prefill only. Gold-standard export must not treat it as inference.

APIs such as ``document_to_ls_tasks`` / ``item_to_ls_task`` / ``ImageMetadata``
and ``DEFAULT_LS_RESULT_SPECS`` are retained for legacy tests and callers.
V1 rework encoders: ``bboxes_to_ls_rectangle_results``,
``caption_to_ls_textarea_results`` (SEG: ``mask_ref_to_polygon_ls_results``).
SEG geometry via ``mask_root`` remains available; default mode is
polygonlabels (brush RLE via ``SEG_PREFILL_MODE``). Does not wire the V1 CLI
main path or define Label Studio XML.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from mma.common.models import BBox, TaskType

if TYPE_CHECKING:
    from mma.formats.legacy_prelabel.intermediate import (
        PrelabelDocument,
        PrelabelItem,
    )

MODEL_VERSION = "mma-prelabel-1.0"

# Centralized data field names (do not hard-code these strings in builders).
DATA_KEY_IMAGE = "image"
DATA_KEY_MASK_REF = "mask_ref"
DATA_KEY_DIAGNOSIS_TEXT = "diagnosis_text"
DATA_KEY_IMAGE_ID = "image_id"
DATA_KEY_PACKAGE_ID = "package_id"
DATA_KEY_BATCH_ID = "batch_id"

# SEG prediction prefill mode: ``polygon`` (default) or legacy ``brush`` RLE.
SegPrefillMode = Literal["polygon", "brush"]
SEG_PREFILL_MODE: SegPrefillMode = "polygon"

# Default Label Studio control/result names for T2.2.
# T3 XML ``name`` attributes should align with these; adjust in one place later.
DEFAULT_LS_RESULT_SPECS: dict[TaskType, dict[str, Any]] = {
    TaskType.SEG: {
        "from_name": "seg_mask",
        "to_name": "image",
        "type": "polygonlabels",
        "labels": ("lesion",),
    },
    TaskType.DET: {
        "from_name": "det_bbox",
        "to_name": "image",
        "type": "rectanglelabels",
        "labels": ("object",),
    },
    TaskType.CAP: {
        "from_name": "cap_text",
        "to_name": "image",
        "type": "textarea",
        "labels": (),
    },
}


@dataclass(frozen=True)
class ImageMetadata:
    """Caller-supplied image size for DET pixel → percent conversion."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or not isinstance(self.height, int):
            raise ValueError("ImageMetadata width/height must be int")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"ImageMetadata width/height must be > 0, "
                f"got width={self.width!r}, height={self.height!r}"
            )


def _pixel_bbox_to_percent(
    bbox: BBox,
    metadata: ImageMetadata,
) -> dict[str, float]:
    """Convert a pixel ``BBox`` to Label Studio percent value fields."""

    return {
        "x": bbox.x / metadata.width * 100.0,
        "y": bbox.y / metadata.height * 100.0,
        "width": bbox.width / metadata.width * 100.0,
        "height": bbox.height / metadata.height * 100.0,
        "rotation": 0.0,
    }


def bboxes_to_ls_rectangle_results(
    bboxes: Sequence[BBox],
    metadata: ImageMetadata,
) -> list[dict[str, Any]]:
    """Encode V1 DET boxes as Label Studio rectanglelabels ``result`` entries.

    Empty ``bboxes`` yields ``[]``. Labels come from ``DEFAULT_LS_RESULT_SPECS``.
    """

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.DET]
    labels = list(spec["labels"])
    results: list[dict[str, Any]] = []
    for bbox in bboxes:
        value = _pixel_bbox_to_percent(bbox, metadata)
        value["rectanglelabels"] = labels
        results.append(
            {
                "original_width": metadata.width,
                "original_height": metadata.height,
                "image_rotation": 0,
                "from_name": spec["from_name"],
                "to_name": spec["to_name"],
                "type": spec["type"],
                "value": value,
            }
        )
    return results


def caption_to_ls_textarea_results(caption: str) -> list[dict[str, Any]]:
    """Encode a CAP caption (including ``""``) as one textarea ``result``."""

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]
    return [
        {
            "from_name": spec["from_name"],
            "to_name": spec["to_name"],
            "type": spec["type"],
            "value": {"text": [caption]},
        }
    ]


def _build_common_data(item: PrelabelItem) -> dict[str, Any]:
    return {
        DATA_KEY_IMAGE: item.image_path,
        DATA_KEY_DIAGNOSIS_TEXT: item.diagnosis_text,
        DATA_KEY_IMAGE_ID: item.image_id,
        DATA_KEY_PACKAGE_ID: item.package_id,
        DATA_KEY_BATCH_ID: item.batch_id,
    }


def _normalize_seg_prefill_mode(mode: str | None) -> SegPrefillMode:
    resolved = SEG_PREFILL_MODE if mode is None else mode
    if resolved not in ("polygon", "brush"):
        raise ValueError(
            f"SEG_PREFILL_MODE must be 'polygon' or 'brush', got {resolved!r}"
        )
    return resolved  # type: ignore[return-value]


def _build_seg_results(
    item: PrelabelItem,
    *,
    mask_root: Path | str | None = None,
    image_metadata: ImageMetadata | None = None,
    seg_prefill_mode: SegPrefillMode | None = None,
) -> list[dict[str, Any]]:
    """Build SEG prediction results.

    Without ``mask_root``, returns ``[]`` (T2.2-compatible). With ``mask_root``,
    reads ``mask_ref`` and emits one result per connected component:

    - ``polygon`` (default): polygonlabels percent points (T3.1b polygon)
    - ``brush``: brushlabels RLE (legacy)

    ``data.mask_ref`` is still set by the caller.
    """

    from mma.formats.legacy_prelabel.intermediate import SegPrelabelPayload

    assert isinstance(item.payload, SegPrelabelPayload)
    if mask_root is None:
        return []
    mode = _normalize_seg_prefill_mode(seg_prefill_mode)
    if mode == "brush":
        # Lazy import avoids circular dependency with ``seg_brush``.
        from mma.converters.seg_brush import build_seg_brush_results

        return build_seg_brush_results(
            item,
            mask_root=mask_root,
            image_metadata=image_metadata,
        )
    # Lazy import avoids circular dependency with ``seg_polygon``.
    from mma.converters.seg_polygon import build_seg_polygon_results

    return build_seg_polygon_results(
        item,
        mask_root=mask_root,
        image_metadata=image_metadata,
    )


def _build_det_results(
    item: PrelabelItem,
    metadata: ImageMetadata,
) -> list[dict[str, Any]]:
    from mma.formats.legacy_prelabel.intermediate import DetPrelabelPayload

    assert isinstance(item.payload, DetPrelabelPayload)
    boxes = tuple(
        BBox(x=b.x, y=b.y, width=b.width, height=b.height)
        for b in item.payload.bboxes
    )
    return bboxes_to_ls_rectangle_results(boxes, metadata)


def _build_cap_results(item: PrelabelItem) -> list[dict[str, Any]]:
    from mma.formats.legacy_prelabel.intermediate import CapPrelabelPayload

    assert isinstance(item.payload, CapPrelabelPayload)
    return caption_to_ls_textarea_results(item.payload.caption)


def _require_det_metadata(
    item: PrelabelItem,
    image_metadata: ImageMetadata | None,
) -> ImageMetadata:
    if image_metadata is None:
        raise ValueError(
            "DET conversion requires image_metadata "
            f"(image_id={item.image_id!r}, package_id={item.package_id!r})"
        )
    return image_metadata


def item_to_ls_task(
    item: PrelabelItem,
    *,
    image_metadata: ImageMetadata | None = None,
    mask_root: Path | str | None = None,
    seg_prefill_mode: SegPrefillMode | None = None,
) -> dict[str, Any]:
    """LEGACY: convert one ``PrelabelItem`` to a Label Studio import task dict.

    Not part of V1 first-round ``ls-import``. ``id`` is set to ``image_id`` as
    an auxiliary LS task identifier only. The system association key remains
    ``data.image_id``.

    For DET, ``image_metadata`` is required (pixel → percent).
    For SEG, pass ``mask_root`` to emit geometry prefill; omit it to keep empty
    ``predictions[].result``. Prefill mode defaults to module
    ``SEG_PREFILL_MODE`` (``polygon``); pass ``brush`` for brush RLE.
    Optional SEG ``image_metadata`` is only used to validate mask size when
    provided. CAP ignores ``mask_root`` / ``image_metadata``.
    """

    from mma.formats.legacy_prelabel.intermediate import (
        SegPrelabelPayload,
        assert_payload_matches_task,
    )

    assert_payload_matches_task(item.task_type, item.payload)
    data = _build_common_data(item)

    if item.task_type is TaskType.SEG:
        assert isinstance(item.payload, SegPrelabelPayload)
        data[DATA_KEY_MASK_REF] = item.payload.mask_ref
        result = _build_seg_results(
            item,
            mask_root=mask_root,
            image_metadata=image_metadata,
            seg_prefill_mode=seg_prefill_mode,
        )
    elif item.task_type is TaskType.DET:
        meta = _require_det_metadata(item, image_metadata)
        result = _build_det_results(item, meta)
    elif item.task_type is TaskType.CAP:
        result = _build_cap_results(item)
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError(f"unsupported task type: {item.task_type!r}")

    return {
        "id": item.image_id,
        "data": data,
        "predictions": [
            {
                "model_version": MODEL_VERSION,
                "result": result,
            }
        ],
    }


def document_to_ls_tasks(
    document: PrelabelDocument,
    *,
    image_metadata_by_id: Mapping[str, ImageMetadata] | None = None,
    mask_root: Path | str | None = None,
    seg_prefill_mode: SegPrefillMode | None = None,
) -> list[dict[str, Any]]:
    """LEGACY: convert a ``PrelabelDocument`` to Label Studio import tasks.

    Not part of V1 first-round ``ls-import``. When ``document.task_type`` is
    DET, ``image_metadata_by_id`` must map every item ``image_id`` to an
    ``ImageMetadata``. For SEG, optional ``mask_root`` enables geometry
    prefill; ``seg_prefill_mode`` selects polygon (default) or brush RLE.
    """

    metadata_map = image_metadata_by_id or {}
    tasks: list[dict[str, Any]] = []

    for item in document.items:
        if item.task_type is not document.task_type:
            raise ValueError(
                f"item task_type {item.task_type.value} does not match "
                f"document {document.task_type.value} "
                f"(image_id={item.image_id!r}, package_id={item.package_id!r})"
            )

        meta: ImageMetadata | None = None
        if document.task_type is TaskType.DET:
            if item.image_id not in metadata_map:
                raise ValueError(
                    "DET conversion missing image_metadata for "
                    f"image_id={item.image_id!r}, package_id={item.package_id!r}"
                )
            meta = metadata_map[item.image_id]
        elif document.task_type is TaskType.SEG:
            meta = metadata_map.get(item.image_id)

        tasks.append(
            item_to_ls_task(
                item,
                image_metadata=meta,
                mask_root=mask_root,
                seg_prefill_mode=seg_prefill_mode,
            )
        )

    return tasks
