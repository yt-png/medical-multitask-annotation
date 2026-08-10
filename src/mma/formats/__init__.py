"""Unified prelabel intermediate formats (P2 / T2.1)."""

from mma.formats.intermediate import (
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
