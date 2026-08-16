"""LEGACY converters: prelabel intermediate → downstream import formats.

Historical / reference only. **Not used by V1 first-round** ``ls-import``
(empty tasks are built in ``importers.build_ls_tasks``). Public APIs such as
``document_to_ls_tasks``, ``item_to_ls_task``, ``ImageMetadata``, and
``DEFAULT_LS_RESULT_SPECS`` remain available for legacy tests and callers.
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
