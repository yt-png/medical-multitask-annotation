"""Resolve Label Studio effective annotation result (human vs prediction).

Used by ``parse_ls_export`` (warning + shared policy) and
``extract_ls_raw_results`` (legacy rework side-channel).

Does not change ``TaskAnnotationResult`` / ``current/`` JSON schema.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from mma.common.models import TaskType
from mma.converters.to_labelstudio import DEFAULT_LS_RESULT_SPECS

logger = logging.getLogger(__name__)

CHOICE_FROM_NAMES = frozenset({"human_confirmed", "needs_rework"})
EffectiveSource = Literal["annotation", "prediction_fallback", "empty"]


@dataclass(frozen=True)
class EffectiveLsResult:
    """Effective LS ``result`` list plus tracing copies of the raw sides."""

    image_id: str
    task_type: TaskType
    effective_result: tuple[dict[str, Any], ...]
    annotation_result: tuple[dict[str, Any], ...]
    prediction_result: tuple[dict[str, Any], ...]
    source: EffectiveSource
    human_cleared: bool


def resolve_effective_result(
    task: Mapping[str, Any],
    *,
    task_type: TaskType,
    image_id: str | None = None,
    annotation: Mapping[str, Any] | None = None,
) -> EffectiveLsResult:
    """Build effective ``result`` for one LS task.

    Rules:

    1. Annotation has task payload controls → use annotation.result
    2. Annotation has only Choices (no task payload), prediction has task
       payload, and the annotator did **not** intentionally clear via
       ``annotation.prediction`` link → prediction task controls + annotation
       Choices
    3. Intentional clear (``annotation.prediction`` set, no task payload) →
       keep annotation.result only (no prediction fallback)
    4. Otherwise → annotation.result (may be Choices-only / empty task payload)
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    resolved_id = image_id
    if resolved_id is None:
        data = task.get("data")
        if isinstance(data, dict):
            raw_id = data.get("image_id")
            if isinstance(raw_id, str) and raw_id.strip():
                resolved_id = raw_id.strip()
    if not resolved_id:
        raise ValueError("image_id is required for resolve_effective_result")

    if annotation is None:
        from mma.exporters.parse_ls_export import _select_annotation

        annotation = _select_annotation(
            task.get("annotations"), image_id=resolved_id
        )

    ann_raw = annotation.get("result")
    if not isinstance(ann_raw, list):
        raise ValueError(
            f"annotation result must be a list (image_id={resolved_id!r})"
        )
    annotation_result = _deepcopy_result_list(ann_raw, image_id=resolved_id)
    prediction_result = _deepcopy_result_list(
        _prediction_result_items(task),
        image_id=resolved_id,
    )

    control = DEFAULT_LS_RESULT_SPECS[task_type]["from_name"]
    ann_payload = _task_payload_entries(annotation_result, control=control)
    pred_payload = _task_payload_entries(prediction_result, control=control)
    choices = _choice_entries(annotation_result)

    human_cleared = _is_human_cleared(
        annotation,
        has_ann_payload=bool(ann_payload),
    )

    if ann_payload:
        source: EffectiveSource = "annotation"
        effective = annotation_result
    elif human_cleared:
        source = "annotation"
        effective = annotation_result
    elif pred_payload:
        source = "prediction_fallback"
        effective = tuple(list(pred_payload) + list(choices))
    elif annotation_result:
        source = "empty"
        effective = annotation_result
    else:
        source = "empty"
        effective = ()

    if source == "prediction_fallback" and _annotation_has_human_confirmed(
        annotation_result
    ):
        logger.warning(
            "human_confirmed set but annotation has no task payload; "
            "using prediction fallback "
            "(image_id=%r, task_type=%s)",
            resolved_id,
            task_type.value,
        )

    return EffectiveLsResult(
        image_id=resolved_id,
        task_type=task_type,
        effective_result=effective,
        annotation_result=annotation_result,
        prediction_result=prediction_result,
        source=source,
        human_cleared=human_cleared,
    )


def _is_human_cleared(
    annotation: Mapping[str, Any],
    *,
    has_ann_payload: bool,
) -> bool:
    """True when annotator accepted a prediction then cleared all task geometry.

    Signal: ``annotation.prediction`` is not null and annotation has no task
    payload controls (DET/SEG). CAP clear is represented by an empty
    ``cap_text`` entry (payload present), so it does not use this path.
    """

    if has_ann_payload:
        return False
    return annotation.get("prediction") is not None


def _annotation_has_human_confirmed(
    annotation_result: Sequence[Mapping[str, Any]],
) -> bool:
    for entry in annotation_result:
        if entry.get("from_name") != "human_confirmed":
            continue
        value = entry.get("value")
        if not isinstance(value, dict):
            continue
        choices = value.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        raw = choices[0]
        if isinstance(raw, str) and raw.strip().lower() == "yes":
            return True
    return False


def _task_payload_entries(
    result_items: Sequence[Mapping[str, Any]],
    *,
    control: str,
) -> tuple[dict[str, Any], ...]:
    return tuple(
        dict(entry)
        for entry in result_items
        if entry.get("from_name") == control
    )


def _choice_entries(
    result_items: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        dict(entry)
        for entry in result_items
        if entry.get("from_name") in CHOICE_FROM_NAMES
    )


def _prediction_result_items(task: Mapping[str, Any]) -> list[Any]:
    """Prefer last prediction with a list ``result``; else ``[]``."""

    predictions = task.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        return []
    # Prefer the last prediction that carries an inline result list.
    for prediction in reversed(predictions):
        if not isinstance(prediction, dict):
            continue
        result = prediction.get("result")
        if isinstance(result, list):
            return result
    return []


def _deepcopy_result_list(
    items: Sequence[Any],
    *,
    image_id: str,
) -> tuple[dict[str, Any], ...]:
    copied: list[dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise ValueError(
                f"result entry must be an object (image_id={image_id!r})"
            )
        copied.append(copy.deepcopy(entry))
    return tuple(copied)
