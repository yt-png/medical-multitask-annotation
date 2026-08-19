"""Build rework LS import tasks (P4 CLI glue).

V1 main path: self-contained ``rework/previous_annotations/`` (historical
human annotation). Prefill source is that snapshot only.

Does not read ``prelabels/``. ``export_path`` is ignored for prefill
geometry (deprecated CLI flag). If the snapshot is missing, run
``export-split`` or ``apply-current`` first.
"""

from __future__ import annotations

from pathlib import Path

from mma.common.io import write_json
from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    ls_import_task_dir,
    results_rework_dir,
    validate_batch_id,
)
from mma.exporters.current_annotations import (
    ANNOTATIONS_JSON_NAME,
    read_annotations_json,
)
from mma.exporters.previous_annotations import previous_annotations_json_path
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
    """Build ``rework_tasks.json`` from previous_annotations.

    If ``rework/previous_annotations/<task>.json`` exists → use it
    (``export_path`` ignored for prefill geometry). Prefill is human
    history written into the LS ``predictions`` slot, not model output.

    Else raise: run ``export-split`` / ``apply-current`` first.

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
        raise ValueError(
            "rework/previous_annotations is missing; run export-split "
            "(or apply-current) first "
            f"(expected {prev_path})"
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
    rework = read_annotations_json(
        rework_ann,
        task_type=task_type,
        batch_id=batch_id,
        data_root=data_root,
    )
    return build_rework_ls_tasks(
        rework,
        batch_id=batch_id,
        task_type=task_type,
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
