"""Apply LS export results onto ``results/.../current/`` (P4 CLI glue).

Responsibility (底层 / current 同步)::

    apply-current:  export JSON  →  merge into ``current/``

This is the **shared underlying** sync used by ``export_split_from_export``.
After writing ``current/``, it also full-rebuilds ``normal/`` / ``rework/``
(and rework ``previous_annotations/``) from ``current/`` so the tree stays
consistent — callers that only need classified paths should use
``mma export-split`` instead of running both CLI commands.

Orchestrates ``parse_ls_export`` + ``overwrite_current``, then
``refresh_normal_rework_from_current``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    parse_export_round_from_path,
    results_manual_masks_dir,
    validate_batch_id,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.converters import ImageMetadata
from mma.exporters.cleanup_manual_masks import cleanup_unreferenced_manual_masks
from mma.exporters.fill_missing_from_package import fill_missing_from_package
from mma.exporters.overwrite_current import overwrite_current
from mma.exporters.parse_ls_export import parse_ls_export
from mma.exporters.refresh_normal_rework import refresh_normal_rework_from_current

_TASK_TYPE_MAP = {
    "seg": TaskType.SEG,
    "det": TaskType.DET,
    "cap": TaskType.CAP,
    "SEG": TaskType.SEG,
    "DET": TaskType.DET,
    "CAP": TaskType.CAP,
}


def apply_current_from_export(
    export_path: Path | str,
    *,
    batch_id: str,
    task: str | TaskType,
    data_root: Path | str | None = None,
) -> Path:
    """底层：export → merge ``current/``（并刷新派生的 normal/rework）.

    Role: shared current-sync primitive for P4. Prefer ``export_split_from_export``
    / ``mma export-split`` when you need normal/rework paths; do **not** run
    ``apply-current`` and ``export-split`` back-to-back on the same export
    (export-split already calls this function).

    - Matching ``image_id`` in the export overwrite current entries; others keep
    - After parse, samples in the task package that are in neither this export
      nor existing ``current/`` are filled as empty unconfirmed results (R1)
      so they enter ``rework/``. Export ids not in the package fail the batch.
    - After write, ``normal/`` and ``rework/`` are fully rebuilt from current
      (not from the export subset alone)
    - For SEG, unreferenced ``manual_masks/*_manual.png`` files are removed
      after refresh so disk matches current ``mask_ref``

    Empty parse results still follow ``overwrite_current`` no-op semantics when
    there are no package placeholders; otherwise placeholders are written, then
    bundles refresh from ``current/``.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    task_type = _parse_task_arg(task)
    path = Path(export_path)
    if not path.is_file():
        raise FileNotFoundError(f"LS export not found: {path}")

    metadata: dict[str, ImageMetadata] | None = None
    if task_type is TaskType.DET or task_type is TaskType.SEG:
        image_ids = _peek_export_image_ids(path)
        metadata = _task_image_metadata_by_id(
            cleaned,
            image_ids,
            task_type=task_type,
            data_root=root,
        )

    seg_mask_dir = None
    if task_type is TaskType.SEG:
        seg_mask_dir = results_manual_masks_dir(cleaned, data_root=root)

    export_round = parse_export_round_from_path(path)
    results = parse_ls_export(
        path,
        task_type=task_type,
        image_metadata_by_id=metadata,
        seg_manual_mask_dir=seg_mask_dir,
        export_round=export_round,
    )
    results = fill_missing_from_package(
        results,
        batch_id=cleaned,
        task_type=task_type,
        data_root=root,
        export_round=export_round,
    )
    current_path = overwrite_current(
        results,
        batch_id=cleaned,
        task_type=task_type,
        data_root=root,
    )
    refresh_normal_rework_from_current(
        cleaned,
        task_type,
        data_root=root,
    )
    if task_type is TaskType.SEG:
        cleanup_unreferenced_manual_masks(cleaned, data_root=root)
    return current_path


def _parse_task_arg(task: str | TaskType) -> TaskType:
    if isinstance(task, TaskType):
        return task
    try:
        return _TASK_TYPE_MAP[str(task)]
    except KeyError as exc:
        raise ValueError(f"unsupported task type: {task!r}") from exc


def _peek_export_image_ids(export_path: Path) -> list[str]:
    """Read ``data.image_id`` list before full DET parsing."""

    payload = read_json(export_path)
    if not isinstance(payload, list):
        raise ValueError(f"export must be a JSON array: {export_path}")
    image_ids: list[str] = []
    for index, task in enumerate(payload):
        if not isinstance(task, dict):
            raise ValueError(f"export task at index {index} must be an object")
        data = task.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"export task at index {index} missing data object")
        image_id = data.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError(
                f"export task at index {index} missing data.image_id"
            )
        image_ids.append(image_id.strip())
    return image_ids


def _task_image_metadata_by_id(
    batch_id: str,
    image_ids: list[str],
    *,
    task_type: TaskType,
    data_root: Path,
) -> dict[str, ImageMetadata]:
    """Load image sizes from task-package files.

    DET requires every ``image_id`` to resolve. SEG treats missing package
    images as skippable (empty-mask sizing can use annotation ``original_*``
    or fail later with a clear size error).
    """

    task_key = task_type.value.lower()
    meta: dict[str, ImageMetadata] = {}
    for image_id in image_ids:
        try:
            image_path = resolve_task_image_path(
                batch_id,
                task_key,
                image_id,
                data_root=data_root,
            )
        except ValueError:
            if task_type is TaskType.SEG:
                continue
            raise
        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except OSError as exc:
            raise ValueError(
                f"failed to read image for metadata: {image_path} "
                f"(image_id={image_id!r})"
            ) from exc
        meta[image_id] = ImageMetadata(width=width, height=height)
    return meta
