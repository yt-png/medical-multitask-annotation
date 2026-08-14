"""Split parsed annotation results into normal / rework (T4.2).

Classification uses ``should_rework(human_confirmed, needs_rework)``.
Does not parse Label Studio JSON, write result directories, or build ResultBundle.

Callers that persist bundles should treat ``current/`` as the source of truth
and full-rebuild ``normal/`` / ``rework/`` after each apply (see
``refresh_normal_rework_from_current``).
"""

from __future__ import annotations

from collections.abc import Sequence

from mma.common.models import TaskAnnotationResult, should_rework


def split_by_rework(
    results: Sequence[TaskAnnotationResult],
) -> tuple[tuple[TaskAnnotationResult, ...], tuple[TaskAnnotationResult, ...]]:
    """Split results into ``(normal, rework)``.

    - ``should_rework`` is false → normal
      (``human_confirmed`` and not ``needs_rework``)
    - ``should_rework`` is true → rework
      (``not human_confirmed`` or ``needs_rework``)

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
        if should_rework(
            human_confirmed=item.human_confirmed,
            needs_rework=item.needs_rework,
        ):
            rework.append(item)
        else:
            normal.append(item)
    return tuple(normal), tuple(rework)
