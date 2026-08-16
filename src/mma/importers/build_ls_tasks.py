"""Build Label Studio import task packages (empty first-round tasks)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mma.common.io import read_json, write_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    ls_import_task_dir,
    task_dir_name,
    task_package_dir,
    validate_batch_id,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.converters import DATA_KEY_IMAGE

TASKS_JSON_NAME = "tasks.json"
LOCAL_FILES_PREFIX = "/data/local-files/?d="

_ALLOWED_DATA_KEYS = frozenset(
    {"image", "image_id", "package_id", "diagnosis_text"}
)

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


def build_ls_import_tasks(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
    local_root: Path | str | None = None,
) -> Path:
    """Build empty ``ls_import/<batch>/<task>/tasks.json`` from task packages.

    First-round tasks contain only ``data`` fields (``image``, ``image_id``,
    ``package_id``, ``diagnosis_text``). No ``predictions``, ``mask_ref``, or
    prelabel inputs. Images are referenced (not copied) via
    ``/data/local-files/?d=...`` URLs relative to ``local_root``
    (default: ``data_root``).
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    local = root if local_root is None else Path(local_root)
    task_type = _parse_task_type(task)
    task_key = task_dir_name(task_type)

    package_id, samples = _load_task_package_samples(
        cleaned,
        task_type,
        data_root=root,
    )

    image_paths_by_id: dict[str, Path] = {}
    tasks: list[dict[str, Any]] = []
    for sample in samples:
        image_id = sample["image_id"]
        image_paths_by_id[image_id] = resolve_task_image_path(
            cleaned,
            task_key,
            image_id,
            data_root=root,
        )
        tasks.append(
            {
                "data": {
                    "image": "",
                    "image_id": image_id,
                    "package_id": package_id,
                    "diagnosis_text": sample["diagnosis_text"],
                }
            }
        )

    tasks = rewrite_task_image_urls(
        tasks,
        image_paths_by_id=image_paths_by_id,
        local_root=local,
    )
    for task_obj in tasks:
        data_keys = set(task_obj.get("data") or {})
        if data_keys != _ALLOWED_DATA_KEYS:
            raise ValueError(
                f"empty LS task data keys must be {_ALLOWED_DATA_KEYS}, "
                f"got {sorted(data_keys)}"
            )
        if "predictions" in task_obj:
            raise ValueError("first-round LS tasks must not include predictions")

    out_dir = ls_import_task_dir(cleaned, task_key, data_root=root)
    out_path = out_dir / TASKS_JSON_NAME
    write_json(out_path, tasks)
    return out_path.resolve()


def _load_task_package_samples(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path,
) -> tuple[str, list[dict[str, str]]]:
    """Load ``package_id`` and ordered samples from task-package ``manifest.json``."""

    package_dir = task_package_dir(batch_id, task_type, data_root=data_root)
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"task package manifest not found: {manifest_path} "
            f"(batch_id={batch_id!r}, task={task_dir_name(task_type)!r})"
        )
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError(f"task package manifest must be an object: {manifest_path}")

    raw_package_id = payload.get("package_id")
    if not isinstance(raw_package_id, str) or not raw_package_id.strip():
        raise ValueError(
            f"task package manifest missing non-empty package_id: {manifest_path}"
        )
    package_id = raw_package_id.strip()

    samples_raw = payload.get("samples")
    if not isinstance(samples_raw, list) or not samples_raw:
        raise ValueError(
            f"task package manifest has no samples: {manifest_path}"
        )

    samples: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, sample in enumerate(samples_raw):
        if not isinstance(sample, dict):
            raise ValueError(
                f"task package manifest sample at index {index} must be an object"
            )
        raw_id = sample.get("image_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError(
                f"task package manifest sample at index {index} "
                "missing non-empty image_id"
            )
        image_id = raw_id.strip()
        if image_id in seen:
            raise ValueError(
                f"duplicate image_id in task package manifest: {image_id!r}"
            )
        seen.add(image_id)

        raw_diag = sample.get("diagnosis_text")
        if not isinstance(raw_diag, str):
            raise ValueError(
                f"task package manifest sample at index {index} "
                "missing diagnosis_text string"
            )
        samples.append(
            {
                "image_id": image_id,
                "diagnosis_text": raw_diag,
            }
        )
    return package_id, samples
