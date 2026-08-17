"""Validate that a batch is ready for multitask merge (T5.1).

Read-only. Loads SEG/DET/CAP ``current/`` via ``load_current``.
Does not merge records or write ``final/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mma.common.models import TaskAnnotationResult, TaskType, should_rework_result
from mma.common.paths import default_data_root, processed_batch_dir, validate_batch_id
from mma.exporters.load_current import load_current
from mma.preprocess.load_processed import load_processed_items

_TASK_ORDER = (TaskType.SEG, TaskType.DET, TaskType.CAP)
_MAX_IDS_IN_MESSAGE = 20


def validate_ready(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> None:
    """Assert three-task ``current/`` results are merge-ready.

    Checks (in order):
    1. SEG → DET → CAP ``current/annotations.json`` loadable
       (missing file → ``FileNotFoundError`` from ``load_current``)
    2. No task has an empty item list
    3. No sample with ``should_rework_result`` (unconfirmed, needs_rework,
       or empty/missing task payload)
    4. ``image_id`` sets are identical across the three tasks
    5. That common ``image_id`` set equals ``processed/<batch>/manifest.json``
       (missing processed → ``FileNotFoundError``)

    Readiness does not require ``prelabels/``. Does not merge or write
    ``final/``. Returns ``None`` on success; raises ``ValueError`` on
    logical failures.
    """

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    by_task = _load_three_currents(cleaned, data_root=root)
    _assert_non_empty(by_task)
    _assert_flag_constraints(by_task)
    _assert_image_id_sets_equal(by_task)
    current_ids = {item.image_id for item in by_task[TaskType.SEG]}
    processed_ids = _load_processed_image_ids(cleaned, data_root=root)
    _assert_matches_processed(
        current_ids,
        processed_ids,
        batch_id=cleaned,
    )


def _load_three_currents(
    batch_id: str,
    *,
    data_root: Path,
) -> dict[TaskType, tuple[TaskAnnotationResult, ...]]:
    loaded: dict[TaskType, tuple[TaskAnnotationResult, ...]] = {}
    for task_type in _TASK_ORDER:
        loaded[task_type] = load_current(
            batch_id,
            task_type,
            data_root=data_root,
        )
    return loaded


def _load_processed_image_ids(
    batch_id: str,
    *,
    data_root: Path,
) -> set[str]:
    """Load ``image_id`` set from ``processed/<batch>/manifest.json``."""

    processed_dir = processed_batch_dir(batch_id, data_root=data_root)
    manifest_path = processed_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"processed manifest not found: {manifest_path}")
    records = load_processed_items(processed_dir)
    return {record.image_id for record in records}


def _assert_matches_processed(
    current_ids: set[str],
    processed_ids: set[str],
    *,
    batch_id: str,
) -> None:
    """Require current and processed ``image_id`` sets to be equal."""

    if current_ids == processed_ids:
        return
    only_in_processed = sorted(processed_ids - current_ids)
    only_in_current = sorted(current_ids - processed_ids)
    parts: list[str] = []
    if only_in_processed:
        parts.append(
            "only_in_processed=" + _format_id_list(only_in_processed)
        )
    if only_in_current:
        parts.append("only_in_current=" + _format_id_list(only_in_current))
    raise ValueError(
        f"image_id set does not match processed (batch_id={batch_id!r}); "
        + "; ".join(parts)
    )


def _assert_non_empty(
    by_task: dict[TaskType, tuple[TaskAnnotationResult, ...]],
) -> None:
    empty = [t.value for t, items in by_task.items() if len(items) == 0]
    if empty:
        raise ValueError(
            "current annotations must be non-empty for merge readiness; "
            f"empty tasks: {', '.join(empty)}"
        )


def _assert_flag_constraints(
    by_task: dict[TaskType, tuple[TaskAnnotationResult, ...]],
) -> None:
    rework: list[str] = []
    unconfirmed: list[str] = []
    empty_payload: list[str] = []
    for task_type, items in by_task.items():
        for item in items:
            label = f"{task_type.value}:{item.image_id}"
            if not should_rework_result(item):
                continue
            if item.needs_rework:
                rework.append(label)
            if not item.human_confirmed:
                unconfirmed.append(label)
            if item.human_confirmed and not item.needs_rework:
                empty_payload.append(label)

    parts: list[str] = []
    if rework:
        parts.append("needs_rework residual: " + _format_id_list(rework))
    if unconfirmed:
        parts.append("human_confirmed missing: " + _format_id_list(unconfirmed))
    if empty_payload:
        parts.append("empty task payload: " + _format_id_list(empty_payload))
    if parts:
        raise ValueError("batch not ready for merge; " + "; ".join(parts))


def _assert_image_id_sets_equal(
    by_task: dict[TaskType, tuple[TaskAnnotationResult, ...]],
) -> None:
    sets = {
        task_type: {item.image_id for item in items}
        for task_type, items in by_task.items()
    }
    if sets[TaskType.SEG] == sets[TaskType.DET] == sets[TaskType.CAP]:
        return

    common = sets[TaskType.SEG] & sets[TaskType.DET] & sets[TaskType.CAP]
    union = sets[TaskType.SEG] | sets[TaskType.DET] | sets[TaskType.CAP]
    messages: list[str] = []
    for task_type, ids in sets.items():
        only_in_task = sorted(ids - common)
        if only_in_task:
            messages.append(
                f"only_in_{task_type.value}={_format_id_list(only_in_task)}"
            )
    for task_type, ids in sets.items():
        missing = sorted(union - ids)
        if missing:
            messages.append(
                f"missing_in_{task_type.value}={_format_id_list(missing)}"
            )
    raise ValueError(
        "image_id sets differ across SEG/DET/CAP; " + "; ".join(messages)
    )


def _format_id_list(ids: Sequence[str]) -> str:
    total = len(ids)
    shown = list(ids[:_MAX_IDS_IN_MESSAGE])
    text = ", ".join(shown)
    if total > _MAX_IDS_IN_MESSAGE:
        text += f" ... ({total} total)"
    else:
        text += f" ({total} total)"
    return text
