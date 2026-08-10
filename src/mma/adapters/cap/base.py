"""CAP prelabel adapter interface and example (T2.3).

Does not call real LLM / captioning APIs.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from typing import Any

from mma.adapters.context import AdapterContext, build_prelabel_item
from mma.common.models import TaskType
from mma.formats.intermediate import CapPrelabelPayload, PrelabelItem


class CapPrelabelAdapter(ABC):
    """Base CAP adapter: subclasses must implement ``adapt_payload``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> CapPrelabelPayload:
        """Map algorithm raw mapping to ``CapPrelabelPayload``."""

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

        if context.task_type is not TaskType.CAP:
            raise ValueError(
                "CapPrelabelAdapter requires context.task_type=CAP, "
                f"got {context.task_type.value} (image_id={context.image_id!r})"
            )
        if not isinstance(raw, Mapping):
            raise ValueError(
                "raw must be a Mapping "
                f"(image_id={context.image_id!r})"
            )
        payload = self.adapt_payload(raw, context=context)
        return build_prelabel_item(context, payload)


class ExampleCapAdapter(CapPrelabelAdapter):
    """Runnable example: expects ``{\"caption\": \"...\"}`` in ``raw``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> CapPrelabelPayload:
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"raw must be a Mapping (image_id={context.image_id!r})"
            )
        if "caption" not in raw:
            raise ValueError(
                f"CAP raw missing caption (image_id={context.image_id!r})"
            )
        caption = raw["caption"]
        if not isinstance(caption, str):
            raise ValueError(
                f"CAP raw caption must be a string (image_id={context.image_id!r})"
            )
        return CapPrelabelPayload(caption=caption)
