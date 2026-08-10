"""Build Label Studio import task packages (T3.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from mma.common.io import write_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    ls_import_task_dir,
    prelabels_task_dir,
    task_dir_name,
    task_package_dir,
    validate_batch_id,
)
from mma.converters import (
    DATA_KEY_IMAGE,
    ImageMetadata,
    document_to_ls_tasks,
)
from mma.formats import load_prelabel_document

TASKS_JSON_NAME = "tasks.json"
LOCAL_FILES_PREFIX = "/data/local-files/?d="

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".JPG", ".JPEG")

_TASK_TYPE_MAP = {
    "seg": TaskType.SEG,
    "det": TaskType.DET,
    "cap": TaskType.CAP,
    "SEG": TaskType.SEG,
    "DET": TaskType.DET,
    "CAP": TaskType.CAP,
}


def to_local_files_url(relative_posix: str) -> str:
    """Build a Label Studio local-files URL from a posix-relative path."""

    cleaned = relative_posix.lstrip("/")
    if not cleaned:
        raise ValueError("relative path for local-files URL must be non-empty")
    if "\\" in cleaned:
        raise ValueError(
            f"local-files relative path must use forward slashes: {relative_posix!r}"
        )
    return f"{LOCAL_FILES_PREFIX}{cleaned}"


def resolve_task_image_path(
    batch_id: str,
    task: str | TaskType,
    image_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Resolve ``task_packages/.../images/{image_id}.*`` under ``data_root``."""

    package_dir = task_package_dir(batch_id, task, data_root=data_root)
    images_dir = package_dir / "images"
    if not images_dir.is_dir():
        raise ValueError(
            f"task package images directory not found: {images_dir} "
            f"(batch_id={batch_id!r}, image_id={image_id!r})"
        )

    matches = sorted(
        p
        for p in images_dir.iterdir()
        if p.is_file() and p.stem == image_id and p.suffix in _IMAGE_SUFFIXES
    )
    if not matches:
        raise ValueError(
            f"package image missing for image_id={image_id!r}: "
            f"expected under {images_dir}"
        )
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise ValueError(
            f"multiple package images for image_id={image_id!r}: {names}"
        )
    return matches[0].resolve()


def rewrite_task_image_urls(
    tasks: list[dict[str, Any]],
    *,
    image_paths_by_id: dict[str, Path],
    local_root: Path | str,
) -> list[dict[str, Any]]:
    """Rewrite each task ``data.image`` to a local-files URL under ``local_root``."""

    root = Path(local_root).resolve()
    rewritten: list[dict[str, Any]] = []
    for task in tasks:
        data = dict(task.get("data") or {})
        image_id = data.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError("LS task data.image_id must be a non-empty string")
        if image_id not in image_paths_by_id:
            raise ValueError(
                f"no resolved image path for image_id={image_id!r}"
            )
        abs_path = image_paths_by_id[image_id].resolve()
        try:
            relative = abs_path.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"image path is outside local_root: image={abs_path}, "
                f"local_root={root}, image_id={image_id!r}"
            ) from exc
        data[DATA_KEY_IMAGE] = to_local_files_url(relative.as_posix())
        new_task = dict(task)
        new_task["data"] = data
        rewritten.append(new_task)
    return rewritten


def _parse_task_type(task: str | TaskType) -> TaskType:
    if isinstance(task, TaskType):
        return task
    try:
        return _TASK_TYPE_MAP[str(task)]
    except KeyError as exc:
        raise ValueError(f"unsupported task type: {task!r}") from exc


def _det_metadata_for_paths(
    image_paths_by_id: dict[str, Path],
) -> dict[str, ImageMetadata]:
    meta: dict[str, ImageMetadata] = {}
    for image_id, path in image_paths_by_id.items():
        try:
            with Image.open(path) as img:
                width, height = img.size
        except OSError as exc:
            raise ValueError(
                f"failed to read image for metadata: {path} "
                f"(image_id={image_id!r})"
            ) from exc
        meta[image_id] = ImageMetadata(width=width, height=height)
    return meta


def build_ls_import_tasks(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
    local_root: Path | str | None = None,
) -> Path:
    """Build ``ls_import/<batch>/<task>/tasks.json`` for Label Studio import.

    Images are referenced (not copied) via ``/data/local-files/?d=...`` URLs
    relative to ``local_root`` (default: ``data_root``).
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    local = root if local_root is None else Path(local_root)
    task_type = _parse_task_type(task)
    task_key = task_dir_name(task_type)

    prelabels_dir = prelabels_task_dir(cleaned, task_key, data_root=root)
    prelabels_path = prelabels_dir / "prelabels.json"
    if not prelabels_path.is_file():
        raise ValueError(
            f"prelabels.json not found: {prelabels_path} "
            f"(batch_id={cleaned!r}, task={task_key!r})"
        )

    document = load_prelabel_document(prelabels_path)
    if document.task_type is not task_type:
        raise ValueError(
            f"prelabels task_type {document.task_type.value} does not match "
            f"requested {task_type.value} (batch_id={cleaned!r})"
        )

    image_paths_by_id: dict[str, Path] = {}
    for item in document.items:
        image_paths_by_id[item.image_id] = resolve_task_image_path(
            cleaned,
            task_key,
            item.image_id,
            data_root=root,
        )

    if task_type is TaskType.SEG:
        tasks = document_to_ls_tasks(document, mask_root=prelabels_dir)
    elif task_type is TaskType.DET:
        meta = _det_metadata_for_paths(image_paths_by_id)
        tasks = document_to_ls_tasks(document, image_metadata_by_id=meta)
    else:
        tasks = document_to_ls_tasks(document)

    tasks = rewrite_task_image_urls(
        tasks,
        image_paths_by_id=image_paths_by_id,
        local_root=local,
    )

    out_dir = ls_import_task_dir(cleaned, task_key, data_root=root)
    out_path = out_dir / TASKS_JSON_NAME
    write_json(out_path, tasks)
    return out_path.resolve()
