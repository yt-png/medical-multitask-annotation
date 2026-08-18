"""Converters for Label Studio geometry / import helpers.

May emit a Label Studio ``predictions`` field. In **previous_annotations /
rework** flows that field carries **historical human annotation prefill**,
not a model prediction.

V1 rework encoding uses ``bboxes_to_ls_rectangle_results``,
``caption_to_ls_textarea_results``, and ``mask_ref_to_polygon_ls_results``
(imported from the submodules; not re-exported here).

Also retains **LEGACY** prelabel intermediate → LS import APIs (not used by
V1 first-round ``ls-import``; empty tasks come from ``importers.build_ls_tasks``).
Public APIs such as ``document_to_ls_tasks``, ``item_to_ls_task``,
``ImageMetadata``, and ``DEFAULT_LS_RESULT_SPECS`` remain for legacy tests
and rework geometry encoding callers.
"""

from mma.converters.seg_brush import build_seg_brush_results
from mma.converters.seg_polygon import build_seg_polygon_results
from mma.converters.to_labelstudio import (
    DATA_KEY_BATCH_ID,
    DATA_KEY_DIAGNOSIS_TEXT,
    DATA_KEY_IMAGE,
    DATA_KEY_IMAGE_ID,
    DATA_KEY_MASK_REF,
    DATA_KEY_PACKAGE_ID,
    DEFAULT_LS_RESULT_SPECS,
    MODEL_VERSION,
    SEG_PREFILL_MODE,
    ImageMetadata,
    document_to_ls_tasks,
    item_to_ls_task,
)

__all__ = [
    "DATA_KEY_BATCH_ID",
    "DATA_KEY_DIAGNOSIS_TEXT",
    "DATA_KEY_IMAGE",
    "DATA_KEY_IMAGE_ID",
    "DATA_KEY_MASK_REF",
    "DATA_KEY_PACKAGE_ID",
    "DEFAULT_LS_RESULT_SPECS",
    "MODEL_VERSION",
    "SEG_PREFILL_MODE",
    "ImageMetadata",
    "build_seg_brush_results",
    "build_seg_polygon_results",
    "document_to_ls_tasks",
    "item_to_ls_task",
]
