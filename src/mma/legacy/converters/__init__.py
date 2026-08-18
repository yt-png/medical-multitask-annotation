"""LEGACY: prelabel intermediate → Label Studio import conversion.

Not part of the V1 runtime path. V1 CLI / importers / exporters / merge
must not import this package. Geometry types such as ``ImageMetadata``
remain on ``mma.converters``.
"""

from mma.legacy.converters.to_labelstudio import (
    MODEL_VERSION,
    SEG_PREFILL_MODE,
    document_to_ls_tasks,
    item_to_ls_task,
)

__all__ = [
    "MODEL_VERSION",
    "SEG_PREFILL_MODE",
    "document_to_ls_tasks",
    "item_to_ls_task",
]
