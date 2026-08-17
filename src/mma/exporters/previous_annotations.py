"""Write / read self-contained rework ``previous_annotations/`` snapshots.

Output is a **human annotation snapshot** (from
``TaskAnnotationResult.annotation``), **not** a model prediction.
Business rule: ``previous_annotations`` ≠ prediction. When rework-import
maps this snapshot into a Label Studio ``predictions`` field, that field is
only a UI prefill slot for historical human results.

Built from ``TaskAnnotationResult.annotation`` only (no LS export dependency).
Layout::

    results/<batch>/<task>/rework/previous_annotations/
        <task>.json
        masks/                 # SEG only: copied mask PNGs
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mma.common.io import read_json, write_json
from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import (
    default_data_root,
    results_rework_dir,
    task_dir_name,
    validate_batch_id,
)
from mma.common.seg_mask_paths import resolve_current_seg_mask_path
from mma.converters.to_labelstudio import DEFAULT_LS_RESULT_SPECS
from mma.formats.legacy_prelabel.intermediate import (
    SCHEMA_VERSION,
    PrelabelItem,
    SegPrelabelPayload,
)

PREVIOUS_ANNOTATIONS_DIRNAME = "previous_annotations"
PREVIOUS_MASKS_DIRNAME = "masks"


def previous_annotations_dir(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``.../rework/previous_annotations`` (human-history pack root)."""

    return (
        results_rework_dir(batch_id, task_type, data_root=data_root)
        / PREVIOUS_ANNOTATIONS_DIRNAME
    )


def previous_annotations_json_path(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path | str | None = None,
) -> Path:
    """Return ``.../previous_annotations/<task>.json`` (human snapshot file)."""

    name = f"{task_dir_name(task_type)}.json"
    return previous_annotations_dir(
        batch_id, task_type, data_root=data_root
    ) / name


def write_previous_annotations(
    rework_items: Sequence[TaskAnnotationResult],
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path | str | None = None,
) -> Path:
    """Overwrite ``previous_annotations/<task>.json`` (and SEG masks).

    Snapshot source is human ``TaskAnnotationResult.annotation`` only
    (``previous_annotations`` ≠ model / prelabel prediction).

    Empty ``rework_items`` writes ``[]`` and clears any prior SEG mask copies.
    Returns the JSON path.
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    out_dir = previous_annotations_dir(cleaned, task_type, data_root=root)
    out_path = previous_annotations_json_path(
        cleaned, task_type, data_root=root
    )
    masks_dir = out_dir / PREVIOUS_MASKS_DIRNAME

    _reset_previous_dir(out_dir, masks_dir=masks_dir, task_type=task_type)

    validated = _validate_rework_items(rework_items, task_type=task_type)
    if task_type is TaskType.DET:
        payload = [_det_entry(item) for item in validated]
    elif task_type is TaskType.CAP:
        payload = [_cap_entry(item) for item in validated]
    elif task_type is TaskType.SEG:
        payload = [
            _seg_entry(
                item,
                batch_id=cleaned,
                data_root=root,
                masks_dir=masks_dir,
            )
            for item in validated
        ]
    else:  # pragma: no cover
        raise ValueError(f"unsupported task type: {task_type!r}")

    write_json(out_path, payload)
    return out_path.resolve()


def load_previous_annotations(
    batch_id: str,
    task_type: TaskType,
    *,
    data_root: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Load human-history ``previous_annotations/<task>.json`` by ``image_id``.

    Does not read ``prelabels/``. Raises ``FileNotFoundError`` when missing.
    """

    path = previous_annotations_json_path(
        batch_id, task_type, data_root=data_root
    )
    if not path.is_file():
        raise FileNotFoundError(f"previous annotations not found: {path}")
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(
            f"previous annotations must be a JSON array: {path}"
        )
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(payload):
        if not isinstance(raw, dict):
            raise ValueError(
                f"previous annotations item at index {index} must be an object"
            )
        image_id = raw.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip():
            raise ValueError(
                f"previous annotations item at index {index} missing image_id"
            )
        image_id = image_id.strip()
        if image_id in by_id:
            raise ValueError(
                f"duplicate image_id in previous annotations: {image_id!r}"
            )
        by_id[image_id] = raw
    return by_id


def _reset_previous_dir(
    out_dir: Path,
    *,
    masks_dir: Path,
    task_type: TaskType,
) -> None:
    if out_dir.is_dir():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if task_type is TaskType.SEG:
        masks_dir.mkdir(parents=True, exist_ok=True)


def _validate_rework_items(
    rework_items: Sequence[TaskAnnotationResult],
    *,
    task_type: TaskType,
) -> list[TaskAnnotationResult]:
    validated: list[TaskAnnotationResult] = []
    seen: set[str] = set()
    for index, item in enumerate(rework_items):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"rework_items[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if item.task_type is not task_type:
            raise ValueError(
                f"item task_type {item.task_type.value} does not match "
                f"requested {task_type.value} (image_id={item.image_id!r})"
            )
        if item.image_id in seen:
            raise ValueError(
                f"duplicate image_id in rework previous batch: "
                f"{item.image_id!r}"
            )
        seen.add(item.image_id)
        validated.append(item)
    return validated


def _det_entry(item: TaskAnnotationResult) -> dict[str, Any]:
    """Serialize DET boxes. ``BBox`` has no label — do not invent one."""

    assert isinstance(item.annotation, DetAnnotation)
    return {
        "image_id": item.image_id,
        "bboxes": [
            {
                "x": box.x,
                "y": box.y,
                "width": box.width,
                "height": box.height,
            }
            for box in item.annotation.bboxes
        ],
    }


def _cap_entry(item: TaskAnnotationResult) -> dict[str, Any]:
    assert isinstance(item.annotation, CapAnnotation)
    return {
        "image_id": item.image_id,
        "caption": item.annotation.caption,
    }


def _seg_entry(
    item: TaskAnnotationResult,
    *,
    batch_id: str,
    data_root: Path,
    masks_dir: Path,
) -> dict[str, Any]:
    assert isinstance(item.annotation, SegAnnotation)
    source = resolve_current_seg_mask_path(
        item.annotation.mask_ref,
        batch_id=batch_id,
        data_root=data_root,
    )
    if not source.is_file():
        raise FileNotFoundError(
            f"SEG mask file not found for image_id={item.image_id!r}: "
            f"{source} (mask_ref={item.annotation.mask_ref!r})"
        )

    dest_name = f"{item.image_id}.png"
    dest = masks_dir / dest_name
    shutil.copy2(source, dest)
    mask_file = f"{PREVIOUS_MASKS_DIRNAME}/{dest_name}"

    polygons = _polygons_from_mask_copy(
        item,
        batch_id=batch_id,
        masks_dir=masks_dir,
        mask_file=mask_file,
    )
    return {
        "image_id": item.image_id,
        "mask_file": mask_file,
        "polygons": polygons,
    }


def _polygons_from_mask_copy(
    item: TaskAnnotationResult,
    *,
    batch_id: str,
    masks_dir: Path,
    mask_file: str,
) -> list[dict[str, Any]]:
    """Build polygon snapshot via ``build_seg_polygon_results`` (no reimplement)."""

    from mma.converters.seg_polygon import build_seg_polygon_results

    assert isinstance(item.annotation, SegAnnotation)
    package_id = item.package_id or f"{batch_id}__seg"
    # PrelabelItem here is legacy encoding reuse only — not reading prelabels/.
    prelabel_item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id=batch_id,
        package_id=package_id,
        task_type=TaskType.SEG,
        image_id=item.image_id,
        diagnosis_text="(rework-snapshot)",
        payload=SegPrelabelPayload(mask_ref=mask_file),
    )
    # mask_root = previous_annotations dir (parent of masks/)
    mask_root = masks_dir.parent
    results = build_seg_polygon_results(
        prelabel_item,
        mask_root=mask_root,
    )
    polygons: list[dict[str, Any]] = []
    for entry in results:
        value = entry.get("value")
        if not isinstance(value, dict):
            continue
        points = value.get("points")
        if not isinstance(points, list):
            continue
        poly: dict[str, Any] = {"points": points}
        # Label comes from converter DEFAULT_LS_RESULT_SPECS, not BBox/annotation.
        labels = value.get("polygonlabels")
        if isinstance(labels, list) and labels:
            raw_label = labels[0]
            if isinstance(raw_label, str) and raw_label.strip():
                poly["label"] = raw_label.strip()
        polygons.append(poly)
    return polygons


def build_ls_prediction_results_from_previous(
    entry: Mapping[str, Any],
    *,
    task_type: TaskType,
    image_id: str,
    previous_root: Path,
    image_width: int | None = None,
    image_height: int | None = None,
    package_id: str = "rework",
    batch_id: str = "rework",
) -> list[dict[str, Any]]:
    """Build LS ``predictions[].result`` prefill from one human snapshot entry.

    The word ``prediction`` in this name refers to the Label Studio **field
    slot** used for UI prefill, not model inference. Input is historical
    human ``previous_annotations`` (``previous_annotations`` ≠ prediction).
    Output must never be treated as gold-standard fallback by M6.1
    ``resolve_effective_result``. May reuse legacy ``PrelabelItem`` encoding
    helpers without reading ``prelabels/``.
    """

    if task_type is TaskType.DET:
        return _previous_det_to_ls(
            entry,
            image_id=image_id,
            image_width=image_width,
            image_height=image_height,
            package_id=package_id,
            batch_id=batch_id,
        )
    if task_type is TaskType.CAP:
        return _previous_cap_to_ls(
            entry,
            image_id=image_id,
            package_id=package_id,
            batch_id=batch_id,
        )
    if task_type is TaskType.SEG:
        return _previous_seg_to_ls(
            entry,
            image_id=image_id,
            previous_root=previous_root,
            package_id=package_id,
            batch_id=batch_id,
        )
    raise ValueError(f"unsupported task type: {task_type!r}")  # pragma: no cover


def _previous_det_to_ls(
    entry: Mapping[str, Any],
    *,
    image_id: str,
    image_width: int | None,
    image_height: int | None,
    package_id: str,
    batch_id: str,
) -> list[dict[str, Any]]:
    from mma.converters.to_labelstudio import ImageMetadata, _build_det_results
    from mma.formats.legacy_prelabel.intermediate import DetPrelabelPayload, PrelabelBBox

    if image_width is None or image_height is None:
        raise ValueError(
            f"DET previous→LS requires image size (image_id={image_id!r})"
        )
    bboxes_raw = entry.get("bboxes")
    if not isinstance(bboxes_raw, list):
        raise ValueError(
            f"DET previous entry.bboxes must be a list (image_id={image_id!r})"
        )
    boxes: list[PrelabelBBox] = []
    for index, box in enumerate(bboxes_raw):
        if not isinstance(box, dict):
            raise ValueError(
                f"DET previous bbox[{index}] must be an object "
                f"(image_id={image_id!r})"
            )
        # Optional label in snapshot is ignored for geometry; LS labels come
        # from DEFAULT_LS_RESULT_SPECS inside _build_det_results (not forged
        # onto TaskAnnotationResult / BBox).
        try:
            boxes.append(
                PrelabelBBox(
                    x=float(box["x"]),
                    y=float(box["y"]),
                    width=float(box["width"]),
                    height=float(box["height"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"DET previous bbox[{index}] invalid "
                f"(image_id={image_id!r})"
            ) from exc

    # PrelabelItem / PrelabelBBox: legacy encoding reuse only (not prelabels/).
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id=batch_id,
        package_id=package_id,
        task_type=TaskType.DET,
        image_id=image_id,
        diagnosis_text="(rework-snapshot)",
        payload=DetPrelabelPayload(bboxes=tuple(boxes)),
    )
    return _build_det_results(
        item,
        ImageMetadata(width=image_width, height=image_height),
    )


def _previous_cap_to_ls(
    entry: Mapping[str, Any],
    *,
    image_id: str,
    package_id: str,
    batch_id: str,
) -> list[dict[str, Any]]:
    from mma.converters.to_labelstudio import _build_cap_results
    from mma.formats.legacy_prelabel.intermediate import CapPrelabelPayload

    caption = entry.get("caption")
    if not isinstance(caption, str):
        raise ValueError(
            f"CAP previous entry.caption must be a string "
            f"(image_id={image_id!r})"
        )
    # CapPrelabelPayload rejects empty; empty is a valid human-clear snapshot.
    if not caption.strip():
        spec = DEFAULT_LS_RESULT_SPECS[TaskType.CAP]
        return [
            {
                "from_name": spec["from_name"],
                "to_name": spec["to_name"],
                "type": spec["type"],
                "value": {"text": [""]},
            }
        ]
    # PrelabelItem: legacy encoding reuse only (not reading prelabels/).
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id=batch_id,
        package_id=package_id,
        task_type=TaskType.CAP,
        image_id=image_id,
        diagnosis_text="(rework-snapshot)",
        payload=CapPrelabelPayload(caption=caption.strip()),
    )
    return _build_cap_results(item)


def _previous_seg_to_ls(
    entry: Mapping[str, Any],
    *,
    image_id: str,
    previous_root: Path,
    package_id: str,
    batch_id: str,
) -> list[dict[str, Any]]:
    from mma.converters.seg_polygon import build_seg_polygon_results

    mask_file = entry.get("mask_file")
    if not isinstance(mask_file, str) or not mask_file.strip():
        raise ValueError(
            f"SEG previous entry.mask_file must be non-empty "
            f"(image_id={image_id!r})"
        )
    mask_file = mask_file.strip().replace("\\", "/")
    # PrelabelItem: legacy encoding reuse only (not reading prelabels/).
    item = PrelabelItem(
        schema_version=SCHEMA_VERSION,
        batch_id=batch_id,
        package_id=package_id,
        task_type=TaskType.SEG,
        image_id=image_id,
        diagnosis_text="(rework-snapshot)",
        payload=SegPrelabelPayload(mask_ref=mask_file),
    )
    return build_seg_polygon_results(item, mask_root=previous_root)
