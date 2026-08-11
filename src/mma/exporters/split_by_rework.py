"""Split parsed annotation results into normal vs rework lists (T4.2).

Classification uses only ``TaskAnnotationResult.needs_rework``.
Does not parse Label Studio JSON, write result directories, or build ResultBundle.
"""

from __future__ import annotations

from collections.abc import Sequence

from mma.common.models import TaskAnnotationResult


def split_by_rework(
    results: Sequence[TaskAnnotationResult],
) -> tuple[tuple[TaskAnnotationResult, ...], tuple[TaskAnnotationResult, ...]]:
    """Split results into ``(normal_results, rework_results)``.

    - ``needs_rework is False`` → normal
    - ``needs_rework is True`` → rework

    Relative order within each group matches the input order.
    Empty input yields ``((), ())``.
    """

    normal: list[TaskAnnotationResult] = []
    rework: list[TaskAnnotationResult] = []
    for index, item in enumerate(results):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"results[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if item.needs_rework:
            rework.append(item)
        else:
            normal.append(item)
    return tuple(normal), tuple(rework)
