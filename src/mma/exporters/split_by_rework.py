"""Split parsed annotation results into normal / rework / pending (T4.2).

Classification uses ``human_confirmed`` and ``needs_rework``.
Does not parse Label Studio JSON, write result directories, or build ResultBundle.
"""

from __future__ import annotations

from collections.abc import Sequence

from mma.common.models import TaskAnnotationResult


def split_by_rework(
    results: Sequence[TaskAnnotationResult],
) -> tuple[
    tuple[TaskAnnotationResult, ...],
    tuple[TaskAnnotationResult, ...],
    tuple[TaskAnnotationResult, ...],
]:
    """Split results into ``(normal, rework, pending)``.

    - ``human_confirmed`` and not ``needs_rework`` → normal
    - ``human_confirmed`` and ``needs_rework`` → rework
    - not ``human_confirmed`` → pending (never normal/rework)

    Relative order within each group matches the input order.
    Empty input yields ``((), (), ())``.
    """

    normal: list[TaskAnnotationResult] = []
    rework: list[TaskAnnotationResult] = []
    pending: list[TaskAnnotationResult] = []
    for index, item in enumerate(results):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"results[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if not item.human_confirmed:
            pending.append(item)
            continue
        if item.needs_rework:
            rework.append(item)
        else:
            normal.append(item)
    return tuple(normal), tuple(rework), tuple(pending)
