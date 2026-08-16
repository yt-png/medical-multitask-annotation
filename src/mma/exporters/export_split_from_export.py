"""Split LS export into normal/rework via ``current/`` (P4 CLI glue).

Responsibility (高级封装)::

    export-split:  apply-current  +  rebuild/return normal/rework paths

Calls ``apply_current_from_export`` (no duplicated parse/overwrite logic),
then returns the ``normal/`` and ``rework/`` annotation paths. Prefer this
CLI when classifying results; do **not** also run ``mma apply-current`` on
the same export (redundant double work).

Does not build rework import tasks.
"""

from __future__ import annotations

from pathlib import Path

from mma.common.models import TaskType
from mma.common.paths import (
    default_data_root,
    results_normal_dir,
    results_rework_dir,
    validate_batch_id,
)
from mma.exporters.apply_current_from_export import apply_current_from_export
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME

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
    """高级封装：``apply_current_from_export`` + 返回 normal/rework 路径.

    Equivalent to ``mma export-split``. Internally only delegates to
    ``apply_current_from_export`` (export → current + refresh bundles), then
    returns ``(normal_path, rework_path)``. Empty sides are ``[]``.

    Classification (from full current after merge) uses
    ``should_rework_result`` via ``refresh_normal_rework_from_current`` /
    ``split_by_rework``:

    - confirmed, not flagged, and effective payload present → normal
    - otherwise (unconfirmed, needs_rework, or empty / missing payload) →
      rework
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    task_type = _parse_task_arg(task)

    apply_current_from_export(
        export_path,
        batch_id=cleaned,
        task=task_type,
        data_root=root,
    )

    normal_path = (
        results_normal_dir(cleaned, task_type, data_root=root) / ANNOTATIONS_JSON_NAME
    )
    rework_path = (
        results_rework_dir(cleaned, task_type, data_root=root) / ANNOTATIONS_JSON_NAME
    )
    return normal_path.resolve(), rework_path.resolve()


def _parse_task_arg(task: str | TaskType) -> TaskType:
    if isinstance(task, TaskType):
        return task
    try:
        return _TASK_TYPE_MAP[str(task)]
    except KeyError as exc:
        raise ValueError(f"unsupported task type: {task!r}") from exc
