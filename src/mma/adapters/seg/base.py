"""SEG prelabel adapter interface and example (T2.3).

Does not call real segmentation algorithms.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from typing import Any

from mma.adapters.context import AdapterContext, build_prelabel_item
from mma.common.models import TaskType
from mma.formats.intermediate import PrelabelItem, SegPrelabelPayload


class SegPrelabelAdapter(ABC):
    """Base SEG adapter: subclasses must implement ``adapt_payload``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> SegPrelabelPayload:
        """Map algorithm raw mapping to ``SegPrelabelPayload``."""

        raise NotImplementedError(
            f"{type(self).__name__}.adapt_payload is not implemented "
            f"(image_id={context.image_id!r})"
        )

    def adapt_item(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> PrelabelItem:
        """Adapt payload then attach caller-injected envelope fields."""

        if context.task_type is not TaskType.SEG:
            raise ValueError(
                "SegPrelabelAdapter requires context.task_type=SEG, "
                f"got {context.task_type.value} (image_id={context.image_id!r})"
            )
        if not isinstance(raw, Mapping):
            raise ValueError(
                "raw must be a Mapping "
                f"(image_id={context.image_id!r})"
            )
        payload = self.adapt_payload(raw, context=context)
        return build_prelabel_item(context, payload)


class ExampleSegAdapter(SegPrelabelAdapter):
    """Runnable example: expects ``{\"mask_ref\": \"...\"}`` in ``raw``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> SegPrelabelPayload:
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"raw must be a Mapping (image_id={context.image_id!r})"
            )
        if "mask_ref" not in raw:
            raise ValueError(
                f"SEG raw missing mask_ref (image_id={context.image_id!r})"
            )
        mask_ref = raw["mask_ref"]
        if not isinstance(mask_ref, str):
            raise ValueError(
                f"SEG raw mask_ref must be a string (image_id={context.image_id!r})"
            )
        return SegPrelabelPayload(mask_ref=mask_ref)
