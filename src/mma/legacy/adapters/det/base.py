"""DET prelabel adapter interface and example (T2.3).

Does not call real detection algorithms.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from typing import Any

from mma.legacy.adapters.context import AdapterContext, build_prelabel_item
from mma.common.models import TaskType
from mma.formats.legacy_prelabel.intermediate import DetPrelabelPayload, PrelabelBBox, PrelabelItem


class DetPrelabelAdapter(ABC):
    """Base DET adapter: subclasses must implement ``adapt_payload``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> DetPrelabelPayload:
        """Map algorithm raw mapping to ``DetPrelabelPayload``."""

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

        if context.task_type is not TaskType.DET:
            raise ValueError(
                "DetPrelabelAdapter requires context.task_type=DET, "
                f"got {context.task_type.value} (image_id={context.image_id!r})"
            )
        if not isinstance(raw, Mapping):
            raise ValueError(
                "raw must be a Mapping "
                f"(image_id={context.image_id!r})"
            )
        payload = self.adapt_payload(raw, context=context)
        return build_prelabel_item(context, payload)


class ExampleDetAdapter(DetPrelabelAdapter):
    """Runnable example: expects pixel ``bboxes`` list in ``raw``."""

    def adapt_payload(
        self,
        raw: Mapping[str, Any],
        *,
        context: AdapterContext,
    ) -> DetPrelabelPayload:
        if not isinstance(raw, Mapping):
            raise ValueError(
                f"raw must be a Mapping (image_id={context.image_id!r})"
            )
        if "bboxes" not in raw:
            raise ValueError(
                f"DET raw missing bboxes (image_id={context.image_id!r})"
            )
        bboxes_raw = raw["bboxes"]
        if not isinstance(bboxes_raw, list):
            raise ValueError(
                f"DET raw bboxes must be a list (image_id={context.image_id!r})"
            )

        boxes: list[PrelabelBBox] = []
        for index, box in enumerate(bboxes_raw):
            if not isinstance(box, Mapping):
                raise ValueError(
                    f"DET raw bboxes[{index}] must be an object "
                    f"(image_id={context.image_id!r})"
                )
            try:
                boxes.append(
                    PrelabelBBox(
                        x=float(box["x"]),
                        y=float(box["y"]),
                        width=float(box["width"]),
                        height=float(box["height"]),
                    )
                )
            except KeyError as exc:
                raise ValueError(
                    f"DET raw bboxes[{index}] missing field {exc.args[0]!r} "
                    f"(image_id={context.image_id!r})"
                ) from exc
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"DET raw bboxes[{index}] invalid values "
                    f"(image_id={context.image_id!r}): {exc}"
                ) from exc

        return DetPrelabelPayload(bboxes=tuple(boxes))
