"""Multitask merge package (P5)."""

from mma.merge.materialize_final_seg import (
    FINAL_SEG_MASK_REL_DIR,
    assert_final_seg_mask_contract,
    final_seg_mask_ref,
    materialize_final_seg_mask,
    materialize_final_seg_masks,
)
from mma.merge.merge_multitask import assert_no_missing_tasks, merge_multitask
from mma.merge.merge_to_final import (
    FINAL_IMAGE_REL_DIR,
    assert_final_relative_paths,
    final_image_path,
    merge_to_final,
)
from mma.merge.validate_ready import validate_ready
from mma.merge.write_final import FINAL_MANIFEST_NAME, write_final_manifest

__all__ = [
    "FINAL_IMAGE_REL_DIR",
    "FINAL_MANIFEST_NAME",
    "FINAL_SEG_MASK_REL_DIR",
    "assert_final_relative_paths",
    "assert_final_seg_mask_contract",
    "assert_no_missing_tasks",
    "final_image_path",
    "final_seg_mask_ref",
    "materialize_final_seg_mask",
    "materialize_final_seg_masks",
    "merge_multitask",
    "merge_to_final",
    "validate_ready",
    "write_final_manifest",
]
