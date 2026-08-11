"""Write multitask merge results to ``final/<batch_id>/manifest.json`` (T5.4).

Does not call ``merge_multitask`` or read ``current/``; callers pass complete
``MergedMultitaskRecord`` tuples.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    SegAnnotation,
)
from mma.common.paths import final_batch_dir, validate_batch_id

FINAL_MANIFEST_NAME = "manifest.json"


def merged_record_to_dict(record: MergedMultitaskRecord) -> dict[str, Any]:
    """Convert one ``MergedMultitaskRecord`` to a JSON-compatible dict."""

    return {
        "image_id": record.image_id,
        "image_path": record.image_path,
        "diagnosis_text": record.diagnosis_text,
        "seg": _seg_to_dict(record.seg),
        "det": _det_to_dict(record.det),
        "cap": _cap_to_dict(record.cap),
    }


def write_final_manifest(
    records: Sequence[MergedMultitaskRecord],
    *,
    batch_id: str,
    data_root: Path | str | None = None,
) -> Path:
    """Atomically write ``final/<batch_id>/manifest.json`` (overwrite).

    Payload shape: ``{"batch_id": ..., "items": [...]}``. Item order follows
    ``records``. Returns the manifest path.
    """

    cleaned = validate_batch_id(batch_id)
    out_dir = final_batch_dir(cleaned, data_root=data_root)
    out_path = out_dir / FINAL_MANIFEST_NAME
    payload = {
        "batch_id": cleaned,
        "items": [merged_record_to_dict(item) for item in records],
    }
    _atomic_write_json(out_path, payload)
    return out_path


def _seg_to_dict(seg: SegAnnotation) -> dict[str, Any]:
    return {"mask_ref": seg.mask_ref}


def _det_to_dict(det: DetAnnotation) -> dict[str, Any]:
    return {
        "bboxes": [
            {
                "x": box.x,
                "y": box.y,
                "width": box.width,
                "height": box.height,
            }
            for box in det.bboxes
        ]
    }


def _cap_to_dict(cap: CapAnnotation) -> dict[str, Any]:
    return {"caption": cap.caption}


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
