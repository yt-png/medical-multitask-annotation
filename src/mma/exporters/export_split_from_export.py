"""Split LS export into normal/rework annotation files (P4 CLI glue).

Orchestrates ``parse_ls_export`` + ``split_by_rework`` and writes both sides.
Does not overwrite ``current/`` or build rework import tasks.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskAnnotationResult, TaskType
from mma.common.paths import (
    default_data_root,
    results_normal_dir,
    results_rework_dir,
    validate_batch_id,
)
from mma.converters import ImageMetadata
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    task_annotation_result_to_dict,
)
from mma.exporters.parse_ls_export import parse_ls_export
from mma.exporters.split_by_rework import split_by_rework
from mma.importers.build_ls_tasks import resolve_task_image_path

_TASK_TYPE_MAP = {
    "seg": TaskType.SEG,
    "det": TaskType.DET,
    "cap": TaskType.CAP,
    "SEG": TaskType.SEG,
    "DET": TaskType.DET,
    "CAP": TaskType.CAP,
}


def export_split_from_export(
    export_path: Path | str,
    *,
    batch_id: str,
    task: str | TaskType,
    data_root: Path | str | None = None,
) -> tuple[Path, Path]:
    """Parse export, split by rework, write both annotation files.

    Returns ``(normal_annotations_path, rework_annotations_path)``.
    Empty sides are written as JSON arrays ``[]``.
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

    results = parse_ls_export(
        path,
        task_type=task_type,
        image_metadata_by_id=metadata,
    )
    normal, rework = split_by_rework(results)

    normal_path = (
        results_normal_dir(cleaned, task_type, data_root=root)
        / ANNOTATIONS_JSON_NAME
    )
    rework_path = (
        results_rework_dir(cleaned, task_type, data_root=root)
        / ANNOTATIONS_JSON_NAME
    )
    _write_annotations_file(normal_path, normal)
    _write_annotations_file(rework_path, rework)
    return normal_path.resolve(), rework_path.resolve()


def _write_annotations_file(
    path: Path,
    items: Sequence[TaskAnnotationResult],
) -> None:
    payload = [task_annotation_result_to_dict(item) for item in items]
    write_json(path, payload)


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
