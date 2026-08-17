"""Legacy prelabel intermediate formats (historical / reference).

Not part of the V1 runtime schema. Prefer ``mma.formats.task_schema`` and
``mma.formats.annotation_schema`` for V1 types.
"""

from mma.formats.legacy_prelabel.intermediate import (
    SCHEMA_VERSION,
    CapPrelabelPayload,
    DetPrelabelPayload,
    PrelabelBBox,
    PrelabelDocument,
    PrelabelItem,
    PrelabelPayload,
    SegPrelabelPayload,
    assert_payload_matches_task,
    load_prelabel_document,
    prelabel_document_from_dict,
    prelabel_document_to_dict,
    prelabel_item_from_dict,
    prelabel_item_to_dict,
    validate_prelabel_document,
    validate_prelabel_item,
)

__all__ = [
    "SCHEMA_VERSION",
    "CapPrelabelPayload",
    "DetPrelabelPayload",
    "PrelabelBBox",
    "PrelabelDocument",
    "PrelabelItem",
    "PrelabelPayload",
    "SegPrelabelPayload",
    "assert_payload_matches_task",
    "load_prelabel_document",
    "prelabel_document_from_dict",
    "prelabel_document_to_dict",
    "prelabel_item_from_dict",
    "prelabel_item_to_dict",
    "validate_prelabel_document",
    "validate_prelabel_item",
]
