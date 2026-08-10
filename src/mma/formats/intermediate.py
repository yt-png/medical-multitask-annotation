"""Unified SEG/DET/CAP prelabel intermediate format (T2.1).

This layer shields algorithm-specific outputs before Label Studio conversion.
It does not modify ``mma.common.models`` business result contracts.

Association key: ``image_id``. ``image_path`` is optional auxiliary location only
and is not bound to ``task_packages`` path conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from mma.common.io import read_json
from mma.common.models import TaskType

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PrelabelBBox:
    """Axis-aligned box in **pixel** coordinates: x, y, width, height.

    Origin is the image top-left. ``width`` and ``height`` must be positive;
    ``x`` and ``y`` must be non-negative.
    """

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError(
                f"PrelabelBBox x/y must be >= 0, got x={self.x!r}, y={self.y!r}"
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                "PrelabelBBox width/height must be > 0, "
                f"got width={self.width!r}, height={self.height!r}"
            )


@dataclass(frozen=True)
class SegPrelabelPayload:
    """SEG prelabel: mask as a file reference only (no inline encoding)."""

    mask_ref: str

    def __post_init__(self) -> None:
        if not self.mask_ref or not str(self.mask_ref).strip():
            raise ValueError("SegPrelabelPayload.mask_ref must be a non-empty string")


@dataclass(frozen=True)
class DetPrelabelPayload:
    """DET prelabel: zero or more pixel bboxes."""

    bboxes: tuple[PrelabelBBox, ...]


@dataclass(frozen=True)
class CapPrelabelPayload:
    """CAP prelabel text (distinct from original ``diagnosis_text``)."""

    caption: str

    def __post_init__(self) -> None:
        if not self.caption or not str(self.caption).strip():
            raise ValueError("CapPrelabelPayload.caption must be a non-empty string")


PrelabelPayload = Union[SegPrelabelPayload, DetPrelabelPayload, CapPrelabelPayload]


def assert_payload_matches_task(
    task_type: TaskType,
    payload: PrelabelPayload,
) -> None:
    """Ensure prelabel payload type matches the task type."""

    expected: type[PrelabelPayload]
    if task_type is TaskType.SEG:
        expected = SegPrelabelPayload
    elif task_type is TaskType.DET:
        expected = DetPrelabelPayload
    elif task_type is TaskType.CAP:
        expected = CapPrelabelPayload
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError(f"unsupported task type: {task_type!r}")

    if not isinstance(payload, expected):
        raise ValueError(
            f"payload type {type(payload).__name__} does not match "
            f"task type {task_type.value}"
        )


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class PrelabelItem:
    """Single-image prelabel record in the unified intermediate format."""

    schema_version: str
    batch_id: str
    package_id: str
    task_type: TaskType
    image_id: str
    diagnosis_text: str
    payload: PrelabelPayload
    image_path: str | None = None

    def __post_init__(self) -> None:
        validate_prelabel_item(self)


def validate_prelabel_item(item: PrelabelItem) -> None:
    """Validate a single prelabel item (identity fields + task/payload match)."""

    _require_non_empty_str(item.schema_version, "schema_version")
    _require_non_empty_str(item.batch_id, "batch_id")
    _require_non_empty_str(item.package_id, "package_id")
    _require_non_empty_str(item.image_id, "image_id")
    _require_non_empty_str(item.diagnosis_text, "diagnosis_text")
    if item.image_path is not None and (
        not isinstance(item.image_path, str) or not item.image_path.strip()
    ):
        raise ValueError(
            "image_path must be None or a non-empty string "
            f"(image_id={item.image_id!r})"
        )
    if not isinstance(item.task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(item.task_type)!r}")
    assert_payload_matches_task(item.task_type, item.payload)


@dataclass(frozen=True)
class PrelabelDocument:
    """One task-type prelabel document (maps to ``prelabels.json``)."""

    schema_version: str
    batch_id: str
    package_id: str
    task_type: TaskType
    items: tuple[PrelabelItem, ...]

    def __post_init__(self) -> None:
        validate_prelabel_document(self)


def validate_prelabel_document(document: PrelabelDocument) -> None:
    """Validate document metadata, per-item consistency, and unique image_id."""

    _require_non_empty_str(document.schema_version, "schema_version")
    _require_non_empty_str(document.batch_id, "batch_id")
    _require_non_empty_str(document.package_id, "package_id")
    if not isinstance(document.task_type, TaskType):
        raise ValueError(
            f"task_type must be TaskType, got {type(document.task_type)!r}"
        )
    if not document.items:
        raise ValueError("PrelabelDocument.items must not be empty")

    seen: set[str] = set()
    for index, item in enumerate(document.items):
        validate_prelabel_item(item)
        if item.schema_version != document.schema_version:
            raise ValueError(
                f"item[{index}] schema_version {item.schema_version!r} does not "
                f"match document {document.schema_version!r}"
            )
        if item.batch_id != document.batch_id:
            raise ValueError(
                f"item[{index}] batch_id {item.batch_id!r} does not match "
                f"document {document.batch_id!r}"
            )
        if item.package_id != document.package_id:
            raise ValueError(
                f"item[{index}] package_id {item.package_id!r} does not match "
                f"document {document.package_id!r}"
            )
        if item.task_type is not document.task_type:
            raise ValueError(
                f"item[{index}] task_type {item.task_type.value} does not match "
                f"document {document.task_type.value}"
            )
        if item.image_id in seen:
            raise ValueError(
                f"duplicate image_id in document: {item.image_id!r}"
            )
        seen.add(item.image_id)


def _parse_task_type(value: Any) -> TaskType:
    if isinstance(value, TaskType):
        return value
    if not isinstance(value, str):
        raise ValueError(f"task_type must be a string, got {type(value)!r}")
    try:
        return TaskType(value)
    except ValueError as exc:
        raise ValueError(f"unsupported task_type: {value!r}") from exc


def _bbox_from_dict(raw: Any, *, image_id: str | None = None) -> PrelabelBBox:
    suffix = f" (image_id={image_id!r})" if image_id else ""
    if not isinstance(raw, dict):
        raise ValueError(f"bbox must be an object{suffix}")
    try:
        return PrelabelBBox(
            x=float(raw["x"]),
            y=float(raw["y"]),
            width=float(raw["width"]),
            height=float(raw["height"]),
        )
    except KeyError as exc:
        raise ValueError(f"bbox missing field {exc.args[0]!r}{suffix}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid bbox values{suffix}: {exc}") from exc


def _payload_from_dict(
    task_type: TaskType,
    raw: Any,
    *,
    image_id: str | None = None,
) -> PrelabelPayload:
    suffix = f" (image_id={image_id!r})" if image_id else ""
    if not isinstance(raw, dict):
        raise ValueError(f"payload must be an object{suffix}")

    if task_type is TaskType.SEG:
        if "mask_ref" not in raw:
            raise ValueError(f"SEG payload missing mask_ref{suffix}")
        if not isinstance(raw["mask_ref"], str):
            raise ValueError(f"SEG payload.mask_ref must be a string{suffix}")
        return SegPrelabelPayload(mask_ref=raw["mask_ref"])

    if task_type is TaskType.DET:
        if "bboxes" not in raw:
            raise ValueError(f"DET payload missing bboxes{suffix}")
        bboxes_raw = raw["bboxes"]
        if not isinstance(bboxes_raw, list):
            raise ValueError(f"DET payload.bboxes must be a list{suffix}")
        bboxes = tuple(
            _bbox_from_dict(box, image_id=image_id) for box in bboxes_raw
        )
        return DetPrelabelPayload(bboxes=bboxes)

    if task_type is TaskType.CAP:
        if "caption" not in raw:
            raise ValueError(f"CAP payload missing caption{suffix}")
        if not isinstance(raw["caption"], str):
            raise ValueError(f"CAP payload.caption must be a string{suffix}")
        return CapPrelabelPayload(caption=raw["caption"])

    raise ValueError(f"unsupported task_type: {task_type!r}")  # pragma: no cover


def _payload_to_dict(payload: PrelabelPayload) -> dict[str, Any]:
    if isinstance(payload, SegPrelabelPayload):
        return {"mask_ref": payload.mask_ref}
    if isinstance(payload, DetPrelabelPayload):
        return {
            "bboxes": [
                {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                }
                for box in payload.bboxes
            ]
        }
    if isinstance(payload, CapPrelabelPayload):
        return {"caption": payload.caption}
    raise TypeError(f"unsupported payload type: {type(payload)!r}")


def prelabel_item_from_dict(raw: Any) -> PrelabelItem:
    """Parse and validate one ``PrelabelItem`` from a JSON object."""

    if not isinstance(raw, dict):
        raise ValueError("prelabel item must be an object")

    image_id_hint: str | None = None
    if isinstance(raw.get("image_id"), str) and raw["image_id"].strip():
        image_id_hint = raw["image_id"].strip()

    try:
        schema_version = _require_non_empty_str(
            raw.get("schema_version"), "schema_version"
        )
        batch_id = _require_non_empty_str(raw.get("batch_id"), "batch_id")
        package_id = _require_non_empty_str(raw.get("package_id"), "package_id")
        image_id = _require_non_empty_str(raw.get("image_id"), "image_id")
        diagnosis_text = _require_non_empty_str(
            raw.get("diagnosis_text"), "diagnosis_text"
        )
        task_type = _parse_task_type(raw.get("task_type"))
    except ValueError as exc:
        if image_id_hint:
            raise ValueError(f"{exc} (image_id={image_id_hint!r})") from exc
        raise

    image_path_raw = raw.get("image_path")
    image_path: str | None
    if image_path_raw is None:
        image_path = None
    else:
        image_path = _require_non_empty_str(image_path_raw, "image_path")

    if "payload" not in raw:
        raise ValueError(f"prelabel item missing payload (image_id={image_id!r})")

    payload = _payload_from_dict(
        task_type, raw["payload"], image_id=image_id
    )
    return PrelabelItem(
        schema_version=schema_version,
        batch_id=batch_id,
        package_id=package_id,
        task_type=task_type,
        image_id=image_id,
        diagnosis_text=diagnosis_text,
        payload=payload,
        image_path=image_path,
    )


def prelabel_item_to_dict(item: PrelabelItem) -> dict[str, Any]:
    """Serialize one ``PrelabelItem`` to a JSON-ready dict."""

    validate_prelabel_item(item)
    data: dict[str, Any] = {
        "schema_version": item.schema_version,
        "batch_id": item.batch_id,
        "package_id": item.package_id,
        "task_type": item.task_type.value,
        "image_id": item.image_id,
        "diagnosis_text": item.diagnosis_text,
        "payload": _payload_to_dict(item.payload),
    }
    if item.image_path is not None:
        data["image_path"] = item.image_path
    return data


def prelabel_document_from_dict(raw: Any) -> PrelabelDocument:
    """Parse and validate a ``PrelabelDocument`` from a JSON object."""

    if not isinstance(raw, dict):
        raise ValueError("prelabel document must be an object")

    schema_version = _require_non_empty_str(
        raw.get("schema_version"), "schema_version"
    )
    batch_id = _require_non_empty_str(raw.get("batch_id"), "batch_id")
    package_id = _require_non_empty_str(raw.get("package_id"), "package_id")
    task_type = _parse_task_type(raw.get("task_type"))

    items_raw = raw.get("items")
    if not isinstance(items_raw, list):
        raise ValueError("prelabel document items must be a list")
    if not items_raw:
        raise ValueError("prelabel document items must not be empty")

    items = tuple(prelabel_item_from_dict(item) for item in items_raw)
    return PrelabelDocument(
        schema_version=schema_version,
        batch_id=batch_id,
        package_id=package_id,
        task_type=task_type,
        items=items,
    )


def prelabel_document_to_dict(document: PrelabelDocument) -> dict[str, Any]:
    """Serialize a ``PrelabelDocument`` to a JSON-ready dict."""

    validate_prelabel_document(document)
    return {
        "schema_version": document.schema_version,
        "batch_id": document.batch_id,
        "package_id": document.package_id,
        "task_type": document.task_type.value,
        "items": [prelabel_item_to_dict(item) for item in document.items],
    }


def load_prelabel_document(path: Path | str) -> PrelabelDocument:
    """Load and validate ``prelabels.json`` (or any path) from disk."""

    return prelabel_document_from_dict(read_json(path))
