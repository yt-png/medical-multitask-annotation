"""Build rework LS import tasks (P4 CLI glue).

V1 main path: self-contained ``rework/previous_annotations/`` (historical
human annotation). Falls back to the legacy ``--export`` raw side-channel
only when that snapshot is absent.

Does not read ``prelabels/``. When previous snapshots exist, ``export_path``
is ignored for prefill geometry.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    ls_import_task_dir,
    results_manual_masks_dir,
    results_rework_dir,
    validate_batch_id,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.converters import ImageMetadata
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    read_annotations_json,
)
from mma.exporters.extract_ls_raw_results import extract_ls_raw_results
from mma.exporters.parse_ls_export import parse_ls_export
from mma.exporters.previous_annotations import previous_annotations_json_path
from mma.exporters.split_by_rework import split_by_rework
from mma.importers.build_rework_tasks import build_rework_ls_tasks

REWORK_TASKS_JSON_NAME = "rework_tasks.json"

_TASK_TYPE_MAP = {
    "seg": TaskType.SEG,
    "det": TaskType.DET,
    "cap": TaskType.CAP,
    "SEG": TaskType.SEG,
    "DET": TaskType.DET,
    "CAP": TaskType.CAP,
}


def rework_import_from_export(
    export_path: Path | str | None = None,
    *,
    batch_id: str,
    task: str | TaskType,
    data_root: Path | str | None = None,
    local_root: Path | str | None = None,
) -> Path:
    """Build ``rework_tasks.json`` from previous_annotations or legacy export.

    Priority:
    1. If ``rework/previous_annotations/<task>.json`` exists → use it
       (``export_path`` ignored for prefill geometry). Prefill is human
       history written into the LS ``predictions`` slot, not model output.
    2. Else require ``export_path`` and use the legacy raw-export path.

    Does not read ``prelabels/``. Empty rework side writes ``[]``.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    local = root if local_root is None else Path(local_root)
    task_type = _parse_task_arg(task)

    prev_path = previous_annotations_json_path(
        cleaned, task_type, data_root=root
    )
    if prev_path.is_file():
        tasks = _build_from_previous(
            batch_id=cleaned,
            task_type=task_type,
            data_root=root,
            local_root=local,
        )
    else:
        if export_path is None:
            raise ValueError(
                "rework/previous_annotations is missing; provide --export "
                f"for legacy import (expected {prev_path})"
            )
        tasks = _build_from_export(
            export_path,
            batch_id=cleaned,
            task_type=task_type,
            data_root=root,
            local_root=local,
        )

    out_path = (
        ls_import_task_dir(cleaned, task_type, data_root=root)
        / REWORK_TASKS_JSON_NAME
    )
    write_json(out_path, tasks)
    return out_path.resolve()


def _build_from_previous(
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path,
    local_root: Path,
) -> list:
    rework_ann = (
        results_rework_dir(batch_id, task_type, data_root=data_root)
        / ANNOTATIONS_JSON_NAME
    )
    if not rework_ann.is_file():
        raise FileNotFoundError(
            f"rework annotations not found: {rework_ann}"
        )
    rework = read_annotations_json(rework_ann, task_type=task_type)
    return build_rework_ls_tasks(
        rework,
        batch_id=batch_id,
        task_type=task_type,
        prediction_source="previous",
        data_root=data_root,
        local_root=local_root,
    )


def _build_from_export(
    export_path: Path | str,
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path,
    local_root: Path,
) -> list:
    path = Path(export_path)
    if not path.is_file():
        raise FileNotFoundError(f"LS export not found: {path}")

    metadata: dict[str, ImageMetadata] | None = None
    if task_type is TaskType.DET or task_type is TaskType.SEG:
        image_ids = _peek_export_image_ids(path)
        if task_type is TaskType.DET:
            metadata = _det_image_metadata_by_id(
                batch_id,
                image_ids,
                data_root=data_root,
            )
        else:
            metadata = _seg_image_metadata_by_id(
                batch_id,
                image_ids,
                data_root=data_root,
            )

    seg_mask_dir = None
    if task_type is TaskType.SEG:
        seg_mask_dir = results_manual_masks_dir(batch_id, data_root=data_root)

    results = parse_ls_export(
        path,
        task_type=task_type,
        image_metadata_by_id=metadata,
        seg_manual_mask_dir=seg_mask_dir,
    )
    _, rework = split_by_rework(results)
    raw = extract_ls_raw_results(path, task_type=task_type)
    return build_rework_ls_tasks(
        rework,
        batch_id=batch_id,
        task_type=task_type,
        prediction_source="raw",
        raw_results_by_image_id=raw,
        data_root=data_root,
        local_root=local_root,
    )


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


def _seg_image_metadata_by_id(
    batch_id: str,
    image_ids: list[str],
    *,
    data_root: Path,
) -> dict[str, ImageMetadata]:
    """Best-effort SEG sizes from task packages (missing images skipped)."""

    meta: dict[str, ImageMetadata] = {}
    for image_id in image_ids:
        try:
            image_path = resolve_task_image_path(
                batch_id,
                "seg",
                image_id,
                data_root=data_root,
            )
        except ValueError:
            continue
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
