"""V1 converters: Label Studio geometry / field-name helpers.

May emit a Label Studio ``predictions`` field. In **previous_annotations /
rework** flows that field carries **historical human annotation prefill**,
not a model prediction.

V1 rework encoding uses ``bboxes_to_ls_rectangle_results``,
``caption_to_ls_textarea_results``, and ``mask_ref_to_polygon_ls_results``
(imported from the submodules; not re-exported here).

Prelabel intermediate → LS import lives under ``mma.legacy.converters``
(not used by V1 first-round ``ls-import``; empty tasks come from
``importers.build_ls_tasks``).
"""

from mma.converters.to_labelstudio import (
    DATA_KEY_BATCH_ID,
    DATA_KEY_DIAGNOSIS_TEXT,
    DATA_KEY_IMAGE,
    DATA_KEY_IMAGE_ID,
    DATA_KEY_MASK_REF,
    DATA_KEY_PACKAGE_ID,
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
)

__all__ = [
    "DATA_KEY_BATCH_ID",
    "DATA_KEY_DIAGNOSIS_TEXT",
    "DATA_KEY_IMAGE",
    "DATA_KEY_IMAGE_ID",
    "DATA_KEY_MASK_REF",
    "DATA_KEY_PACKAGE_ID",
    "DEFAULT_LS_RESULT_SPECS",
    "ImageMetadata",
]
