"""Shared context for prelabel adapters (T2.3).

Envelope fields are injected by the caller; adapters only map algorithm raw
``Mapping`` payloads into format-layer types.
"""

from __future__ import annotations

from dataclasses import dataclass

from mma.common.models import TaskType
from mma.formats.intermediate import SCHEMA_VERSION, PrelabelItem, PrelabelPayload


def _require_non_empty_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class AdapterContext:
    """Caller-injected envelope for building ``PrelabelItem`` records."""

    batch_id: str
    package_id: str
    task_type: TaskType
    image_id: str
    diagnosis_text: str
    schema_version: str = SCHEMA_VERSION
    image_path: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.schema_version, "schema_version")
        _require_non_empty_str(self.batch_id, "batch_id")
        _require_non_empty_str(self.package_id, "package_id")
        _require_non_empty_str(self.image_id, "image_id")
        _require_non_empty_str(self.diagnosis_text, "diagnosis_text")
        if not isinstance(self.task_type, TaskType):
            raise ValueError(
                f"task_type must be TaskType, got {type(self.task_type)!r}"
            )
        if self.image_path is not None and (
            not isinstance(self.image_path, str) or not self.image_path.strip()
        ):
            raise ValueError(
                "image_path must be None or a non-empty string "
                f"(image_id={self.image_id!r})"
            )


def build_prelabel_item(
    context: AdapterContext,
    payload: PrelabelPayload,
) -> PrelabelItem:
    """Assemble a ``PrelabelItem`` from caller context and adapted payload."""

    return PrelabelItem(
        schema_version=context.schema_version,
        batch_id=context.batch_id,
        package_id=context.package_id,
        task_type=context.task_type,
        image_id=context.image_id,
        diagnosis_text=context.diagnosis_text,
        payload=payload,
        image_path=context.image_path,
    )
