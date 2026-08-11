"""Batch directory path conventions (see docs/data_layout.md)."""

from __future__ import annotations

import re
from pathlib import Path

from mma.common.models import TaskType

_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

_TASK_DIR_NAMES = {
    TaskType.SEG: "seg",
    TaskType.DET: "det",
    TaskType.CAP: "cap",
    "seg": "seg",
    "det": "det",
    "cap": "cap",
    "SEG": "seg",
    "DET": "det",
    "CAP": "cap",
}


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


def final_batch_dir(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/final/{batch_id}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "final" / cleaned


def task_packages_batch_dir(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/task_packages/{batch_id}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "task_packages" / cleaned


def task_dir_name(task: str | TaskType) -> str:
    """Return lowercase task subdirectory name ``seg`` / ``det`` / ``cap``."""

    key: str | TaskType = task if isinstance(task, TaskType) else str(task)
    try:
        return _TASK_DIR_NAMES[key]
    except KeyError as exc:
        raise ValueError(f"unsupported task type for package dir: {task!r}") from exc


def task_package_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/task_packages/{batch_id}/{seg|det|cap}``."""

    return task_packages_batch_dir(batch_id, data_root=data_root) / task_dir_name(
        task
    )


def prelabels_task_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/prelabels/{batch_id}/{seg|det|cap}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "prelabels" / cleaned / task_dir_name(task)


def ls_import_task_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/ls_import/{batch_id}/{seg|det|cap}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "ls_import" / cleaned / task_dir_name(task)


def results_task_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/results/{batch_id}/{seg|det|cap}``."""

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    return root / "results" / cleaned / task_dir_name(task)


def results_current_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/results/{batch_id}/{seg|det|cap}/current``."""

    return results_task_dir(batch_id, task, data_root=data_root) / "current"


def results_normal_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/results/{batch_id}/{seg|det|cap}/normal``."""

    return results_task_dir(batch_id, task, data_root=data_root) / "normal"


def results_rework_dir(
    batch_id: str,
    task: str | TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``{data_root}/results/{batch_id}/{seg|det|cap}/rework``."""

    return results_task_dir(batch_id, task, data_root=data_root) / "rework"
