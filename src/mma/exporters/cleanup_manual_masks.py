"""Remove SEG ``manual_masks/`` files not referenced by ``current/``.

Called after ``apply-current`` refreshes bundles so disk matches the latest
effective ``mask_ref`` set (Requirement 7.8.3 disk hygiene).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mma.common.models import SegAnnotation, TaskAnnotationResult, TaskType
from mma.common.paths import (
    default_data_root,
    results_current_dir,
    results_manual_masks_dir,
    validate_batch_id,
)
from mma.common.seg_mask_paths import MANUAL_MASK_REL_DIR
from mma.converters.seg_brush import MANUAL_MASK_SUFFIX
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.exporters.load_current import load_current

_MANUAL_MASK_PREFIX = f"{MANUAL_MASK_REL_DIR}/"


def cleanup_unreferenced_manual_masks(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> list[Path]:
    """Delete ``*_manual.png`` files under SEG ``manual_masks/`` not in current.

    - Missing ``manual_masks/`` directory → no-op ``[]``
    - Missing ``current/annotations.json`` → no-op ``[]`` (safe)
    - Only deletes files whose name ends with ``_manual.png``
    - Deletion failures raise ``OSError``

    Returns the list of deleted paths (resolved).
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    mask_dir = results_manual_masks_dir(cleaned, data_root=root)
    if not mask_dir.is_dir():
        return []

    current_path = results_current_dir(
        cleaned, TaskType.SEG, data_root=root
    ) / ANNOTATIONS_JSON_NAME
    if not current_path.is_file():
        return []

    items = load_current(cleaned, TaskType.SEG, data_root=root)
    keep = _referenced_manual_mask_names(items)

    deleted: list[Path] = []
    for path in sorted(mask_dir.iterdir()):
        if not path.is_file():
            continue
        if not _is_manual_mask_filename(path.name):
            continue
        if path.name in keep:
            continue
        path.unlink()
        deleted.append(path.resolve())
    return deleted


def _referenced_manual_mask_names(
    items: Sequence[TaskAnnotationResult],
) -> set[str]:
    names: set[str] = set()
    for item in items:
        annotation = item.annotation
        if not isinstance(annotation, SegAnnotation):
            continue
        ref = str(annotation.mask_ref).strip().replace("\\", "/")
        if not ref.startswith(_MANUAL_MASK_PREFIX):
            continue
        basename = Path(ref).name
        if _is_manual_mask_filename(basename):
            names.add(basename)
    return names


def _is_manual_mask_filename(name: str) -> bool:
    return name.endswith(MANUAL_MASK_SUFFIX) and name != MANUAL_MASK_SUFFIX
