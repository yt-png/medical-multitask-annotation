"""V1 Label Studio geometry helpers (rework / export encoding).

Rework prefill may encode **previous human** masks / boxes / text for
display. Label Studio field name ``predictions`` ≠ model inference; gold-
standard export must not treat it as inference.

Prelabel intermediate → LS import lives under ``mma.legacy.converters``
and is not part of this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from mma.common.models import BBox, TaskType

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
