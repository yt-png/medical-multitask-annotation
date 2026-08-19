"""Resolve current-stage SEG ``mask_ref`` paths (shared by P4 / P5).

V1 resolves only under ``results/<batch>/seg/`` (``manual_masks/...``).
Does not fall back to ``prelabels/``. Does not materialize final masks or
write previous_annotations copies.

``has_foreground`` is computed only from mask pixels
(``compute_has_foreground``). This module does not construct annotations.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
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
    - any other relative ref (including legacy ``masks/...`` under prelabels)
      → ``ValueError`` (no ``prelabels/`` fallback)
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

    raise ValueError(
        "SEG mask_ref must start with "
        f"{MANUAL_MASK_REL_DIR!r}/ under results/<batch>/seg/; "
        "legacy prelabels/masks paths are not a V1 fallback "
        f"(mask_ref={ref!r})"
    )


def _assert_under_base(path: Path, base: Path, *, mask_ref: str) -> None:
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"SEG mask_ref escapes expected root: mask_ref={mask_ref!r}, "
            f"resolved={path}, base={base}"
        ) from exc


def compute_has_foreground(
    mask_ref: str | None,
    *,
    mask_path: Path | str | None = None,
    mask_root: Path | str | None = None,
    batch_id: str | None = None,
    data_root: Path | str | None = None,
) -> bool:
    """Return whether the SEG mask file contains any foreground pixel.

    Source of truth is mask **content**, not ``mask_ref`` presence and not a
    JSON ``has_foreground`` field. Empty / blank ``mask_ref`` → False.
    Missing or unreadable file → False.

    File resolution order: ``mask_path``; else ``mask_root / mask_ref``;
    else current-stage path from ``batch_id``.
    """

    if mask_ref is None or not str(mask_ref).strip():
        return False

    path = _locate_mask_file_for_foreground(
        str(mask_ref).strip().replace("\\", "/"),
        mask_path=mask_path,
        mask_root=mask_root,
        batch_id=batch_id,
        data_root=data_root,
    )
    if path is None or not path.is_file():
        return False
    return _png_has_foreground_pixel(path)


def _locate_mask_file_for_foreground(
    mask_ref: str,
    *,
    mask_path: Path | str | None,
    mask_root: Path | str | None,
    batch_id: str | None,
    data_root: Path | str | None,
) -> Path | None:
    if mask_path is not None:
        return Path(mask_path)
    if mask_root is not None:
        return _join_under_mask_root(Path(mask_root), mask_ref)
    if batch_id is not None:
        try:
            return resolve_current_seg_mask_path(
                mask_ref, batch_id=batch_id, data_root=data_root
            )
        except ValueError:
            return None
    return None


def _join_under_mask_root(mask_root: Path, mask_ref: str) -> Path | None:
    ref = mask_ref.strip().replace("\\", "/")
    if not ref:
        return None
    if Path(ref).is_absolute() or ref.startswith("/") or ref.startswith(".."):
        return None
    root = mask_root.resolve()
    path = (root / ref).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _png_has_foreground_pixel(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                extrema = img.convert("RGBA").getextrema()
                return bool(extrema[3][1] > 0)
            extrema = img.convert("L").getextrema()
            return bool(extrema[1] > 0)
    except OSError:
        return False
