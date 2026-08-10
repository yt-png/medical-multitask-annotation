"""Convert unified prelabel intermediate format to Label Studio import JSON.

SEG brush RLE prefill (T3.1b) is optional via ``mask_root``. Does not wire CLI
or define Label Studio XML. ``from_name`` / ``to_name`` / ``type`` defaults live
in ``DEFAULT_LS_RESULT_SPECS``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mma.common.models import TaskType
from mma.formats.intermediate import (
    CapPrelabelPayload,
    DetPrelabelPayload,
    PrelabelBBox,
    PrelabelDocument,
    PrelabelItem,
    SegPrelabelPayload,
    assert_payload_matches_task,
)

MODEL_VERSION = "mma-prelabel-1.0"

# Centralized data field names (do not hard-code these strings in builders).
DATA_KEY_IMAGE = "image"
DATA_KEY_MASK_REF = "mask_ref"
DATA_KEY_DIAGNOSIS_TEXT = "diagnosis_text"
DATA_KEY_IMAGE_ID = "image_id"
DATA_KEY_PACKAGE_ID = "package_id"
DATA_KEY_BATCH_ID = "batch_id"

# Default Label Studio control/result names for T2.2.
# T3 XML ``name`` attributes should align with these; adjust in one place later.
DEFAULT_LS_RESULT_SPECS: dict[TaskType, dict[str, Any]] = {
    TaskType.SEG: {
        "from_name": "seg_mask",
        "to_name": "image",
        "type": "brushlabels",
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
    bbox: PrelabelBBox,
    metadata: ImageMetadata,
) -> dict[str, float]:
    """Convert a pixel ``PrelabelBBox`` to Label Studio percent value fields."""

    return {
        "x": bbox.x / metadata.width * 100.0,
        "y": bbox.y / metadata.height * 100.0,
        "width": bbox.width / metadata.width * 100.0,
        "height": bbox.height / metadata.height * 100.0,
        "rotation": 0.0,
    }


def _build_common_data(item: PrelabelItem) -> dict[str, Any]:
    return {
        DATA_KEY_IMAGE: item.image_path,
        DATA_KEY_DIAGNOSIS_TEXT: item.diagnosis_text,
        DATA_KEY_IMAGE_ID: item.image_id,
        DATA_KEY_PACKAGE_ID: item.package_id,
        DATA_KEY_BATCH_ID: item.batch_id,
    }


def _build_seg_results(
    item: PrelabelItem,
    *,
    mask_root: Path | str | None = None,
    image_metadata: ImageMetadata | None = None,
) -> list[dict[str, Any]]:
    """Build SEG prediction results.

    Without ``mask_root``, returns ``[]`` (T2.2-compatible). With ``mask_root``,
    reads ``mask_ref`` and emits one brush RLE result per 8-connected component
    (T3.1b). ``data.mask_ref`` is still set by the caller.
    """

    assert isinstance(item.payload, SegPrelabelPayload)
    if mask_root is None:
        return []
    # Lazy import avoids circular dependency with ``seg_brush``.
    from mma.converters.seg_brush import build_seg_brush_results

    return build_seg_brush_results(
        item,
        mask_root=mask_root,
        image_metadata=image_metadata,
    )


def _build_det_results(
    item: PrelabelItem,
    metadata: ImageMetadata,
) -> list[dict[str, Any]]:
    assert isinstance(item.payload, DetPrelabelPayload)
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.DET]
    labels = list(spec["labels"])
    results: list[dict[str, Any]] = []
    for bbox in item.payload.bboxes:
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


def _build_cap_results(item: PrelabelItem) -> list[dict[str, Any]]:
    assert isinstance(item.payload, CapPrelabelPayload)
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]
    return [
        {
            "from_name": spec["from_name"],
            "to_name": spec["to_name"],
            "type": spec["type"],
            "value": {"text": [item.payload.caption]},
        }
    ]


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
) -> dict[str, Any]:
    """Convert one ``PrelabelItem`` to a Label Studio import task dict.

    ``id`` is set to ``image_id`` as an auxiliary LS task identifier only.
    The system association key remains ``data.image_id``.

    For DET, ``image_metadata`` is required (pixel → percent).
    For SEG, pass ``mask_root`` to emit brush RLE prefill (T3.1b); omit it to
    keep empty ``predictions[].result`` (T2.2-compatible). Optional SEG
    ``image_metadata`` is only used to validate mask size when provided.
    CAP ignores ``mask_root`` / ``image_metadata``.
    """

    assert_payload_matches_task(item.task_type, item.payload)
    data = _build_common_data(item)

    if item.task_type is TaskType.SEG:
        assert isinstance(item.payload, SegPrelabelPayload)
        data[DATA_KEY_MASK_REF] = item.payload.mask_ref
        result = _build_seg_results(
            item,
            mask_root=mask_root,
            image_metadata=image_metadata,
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
) -> list[dict[str, Any]]:
    """Convert a ``PrelabelDocument`` to a list of Label Studio import tasks.

    When ``document.task_type`` is DET, ``image_metadata_by_id`` must map every
    item ``image_id`` to an ``ImageMetadata``.
    For SEG, optional ``mask_root`` enables brush RLE prefill for all items.
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
            )
        )

    return tasks
