"""Assign deterministic image_id values to paired image/text rows (T1.2)."""

from __future__ import annotations

from collections.abc import Sequence

from mma.common.ids import generate_image_id
from mma.common.models import ImageRecord, ImageTextPair


def _normalize_key(name: str) -> str:
    """Normalize a full filename for duplicate checks: strip + case-fold."""

    return name.strip().casefold()


def assign_image_ids(
    pairs: Sequence[ImageTextPair],
    batch_id: str,
) -> tuple[ImageRecord, ...]:
    """Bind unique deterministic ``image_id`` values to each pair.

    Does not read images or Excel. Returns an in-memory record list only;
    writing ``processed/`` is deferred to T1.3.
    """

    if not batch_id or not batch_id.strip():
        raise ValueError("batch_id must be a non-empty string")
    batch_id = batch_id.strip()

    if not pairs:
        raise ValueError("pairs must not be empty")

    seen_names: set[str] = set()
    records: list[ImageRecord] = []

    for index, pair in enumerate(pairs, start=1):
        if pair.batch_id is not None and pair.batch_id != batch_id:
            raise ValueError(
                f"pair batch_id {pair.batch_id!r} does not match "
                f"argument batch_id {batch_id!r}"
            )

        key = _normalize_key(pair.source_image_name)
        if not key:
            raise ValueError("source_image_name must not be empty")
        if key in seen_names:
            raise ValueError(
                "duplicate source_image_name after normalization: "
                f"{pair.source_image_name!r}"
            )
        seen_names.add(key)

        records.append(
            ImageRecord(
                image_id=generate_image_id(batch_id, index),
                image_path=pair.image_path,
                diagnosis_text=pair.diagnosis_text,
                batch_id=batch_id,
                source_image_name=pair.source_image_name,
            )
        )

    return tuple(records)
