"""Deterministic ID helpers for the annotation pipeline."""

from __future__ import annotations


def _assert_non_empty_batch_id(batch_id: str) -> None:
    if not batch_id or not batch_id.strip():
        raise ValueError("batch_id must be a non-empty string")


def generate_image_id(batch_id: str, sequence: int) -> str:
    """Build a deterministic image id: ``{batch_id}__{sequence:06d}``.

    ``sequence`` is 1-based. IDs are unique within a batch when sequences
    are unique.
    """

    _assert_non_empty_batch_id(batch_id)
    if sequence < 1:
        raise ValueError(f"sequence must be >= 1, got {sequence}")
    return f"{batch_id.strip()}__{sequence:06d}"
