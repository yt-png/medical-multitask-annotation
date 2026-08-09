"""Batch directory path conventions (see docs/data_layout.md)."""

from __future__ import annotations

import re
from pathlib import Path

_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_batch_id(batch_id: str) -> str:
    """Return a stripped batch_id or raise ``ValueError`` if invalid."""

    if not batch_id or not str(batch_id).strip():
        raise ValueError("batch_id must be a non-empty string")
    cleaned = str(batch_id).strip()
    if not _BATCH_ID_RE.fullmatch(cleaned):
        raise ValueError(
            "batch_id may only contain letters, digits, '-' and '_'; "
            f"got {batch_id!r}"
        )
    return cleaned


def default_data_root() -> Path:
    """Default runtime data root relative to the current working directory."""

    return Path("data")


def processed_batch_dir(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/processed/{batch_id}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "processed" / cleaned
