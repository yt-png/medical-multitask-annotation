"""Apply LS export results onto ``results/.../current/`` (P4 CLI glue).

Orchestrates ``parse_ls_export`` + ``overwrite_current``, then full-rebuilds
``normal/`` and ``rework/`` from ``current/`` (sole source of truth).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    results_manual_masks_dir,
    validate_batch_id,
)
from mma.converters import ImageMetadata
from mma.exporters.overwrite_current import overwrite_current
from mma.exporters.parse_ls_export import parse_ls_export
from mma.exporters.refresh_normal_rework import refresh_normal_rework_from_current
from mma.importers.build_ls_tasks import resolve_task_image_path

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
    """Parse ``export_path``, merge into ``current/``, refresh normal/rework.

    - Matching ``image_id`` in the export overwrite current entries; others keep
    - After write, ``normal/`` and ``rework/`` are fully rebuilt from current
      (not from the export subset alone)

    Empty parse results follow ``overwrite_current`` no-op semantics, then still
    refresh bundles from whatever ``current/`` contains.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    task_type = _parse_task_arg(task)
    path = Path(export_path)
    if not path.is_file():
        raise FileNotFoundError(f"LS export not found: {path}")

    metadata: dict[str, ImageMetadata] | None = None
    if task_type is TaskType.DET:
        image_ids = _peek_export_image_ids(path)
        metadata = _det_image_metadata_by_id(
            cleaned,
            image_ids,
            data_root=root,
        )

    seg_mask_dir = None
    if task_type is TaskType.SEG:
        seg_mask_dir = results_manual_masks_dir(cleaned, data_root=root)

    results = parse_ls_export(
        path,
        task_type=task_type,
        image_metadata_by_id=metadata,
        seg_manual_mask_dir=seg_mask_dir,
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


def _det_image_metadata_by_id(
    batch_id: str,
    image_ids: list[str],
    *,
    data_root: Path,
) -> dict[str, ImageMetadata]:
    meta: dict[str, ImageMetadata] = {}
    for image_id in image_ids:
        image_path = resolve_task_image_path(
            batch_id,
            "det",
            image_id,
            data_root=data_root,
        )
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
