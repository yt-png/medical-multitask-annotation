"""Resolve current-stage SEG ``mask_ref`` paths (shared by P4 / P5).

Does not materialize final masks or write previous_annotations copies.
"""

from __future__ import annotations

from pathlib import Path

from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    prelabels_task_dir,
    results_task_dir,
    validate_batch_id,
)

# Relative directory prefix in SEG ``mask_ref`` for human-confirmed masks
# under ``results/<batch>/seg/``.
MANUAL_MASK_REL_DIR = "manual_masks"


def resolve_current_seg_mask_path(
    mask_ref: str,
    *,
    batch_id: str,
    data_root: Path | str | None = None,
) -> Path:
    """Resolve a ``current/`` SEG ``mask_ref`` to an absolute source file path.

    - ``manual_masks/...`` → ``results/<batch>/seg/manual_masks/...``
    - ``masks/...`` (and other relative refs) → ``prelabels/<batch>/seg/...``
    """

    cleaned_batch = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    ref = str(mask_ref).strip().replace("\\", "/")
    if not ref:
        raise ValueError("SEG mask_ref must be a non-empty string")
    if Path(ref).is_absolute() or ref.startswith("/") or ref.startswith(".."):
        raise ValueError(
            f"SEG mask_ref must be a safe relative path (image mask_ref={ref!r})"
        )

    if ref.startswith(f"{MANUAL_MASK_REL_DIR}/"):
        base = results_task_dir(cleaned_batch, TaskType.SEG, data_root=root)
        path = (base / ref).resolve()
        _assert_under_base(path, base.resolve(), mask_ref=ref)
        return path

    base = prelabels_task_dir(cleaned_batch, TaskType.SEG, data_root=root)
    path = (base / ref).resolve()
    _assert_under_base(path, base.resolve(), mask_ref=ref)
    return path


def _assert_under_base(path: Path, base: Path, *, mask_ref: str) -> None:
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"SEG mask_ref escapes expected root: mask_ref={mask_ref!r}, "
            f"resolved={path}, base={base}"
        ) from exc
