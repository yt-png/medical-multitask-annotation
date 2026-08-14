"""SEG mask ↔ Label Studio polygonlabels (percent points).

Decode: LS ``points`` (%) → ``numpy.uint8`` mask → PNG.
Encode: mask file → connected components → contour → approxPolyDP →
percent points → LS polygon predictions.
Does not remove brush RLE support (``seg_brush``); this module is the default
prefill / decode path for new SEG tasks.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from mma.common.models import TaskType
from mma.converters.seg_brush import (
    MANUAL_MASK_REL_DIR,
    manual_mask_filename,
    manual_mask_ref,
)
from mma.converters.to_labelstudio import (
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
)
from mma.formats.intermediate import PrelabelItem, SegPrelabelPayload

# Relative epsilon for approxPolyDP: fraction of contour perimeter.
DEFAULT_APPROX_EPSILON_RATIO = 0.002


def percent_points_to_pixels(
    points: Sequence[Sequence[float]],
    *,
    width: int,
    height: int,
) -> np.ndarray:
    """Convert LS percent points to an ``(N, 2)`` int32 pixel array."""

    if width <= 0 or height <= 0:
        raise ValueError(
            f"width/height must be > 0, got width={width!r}, height={height!r}"
        )
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        raise ValueError("points must be a sequence of [x, y] pairs")

    rows: list[list[int]] = []
    for index, point in enumerate(points):
        if not isinstance(point, Sequence) or len(point) < 2:
            raise ValueError(
                f"point[{index}] must be [x, y], got {point!r}"
            )
        try:
            x_pct = float(point[0])
            y_pct = float(point[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"point[{index}] coordinates must be numeric, got {point!r}"
            ) from exc
        px = int(round(x_pct / 100.0 * width))
        py = int(round(y_pct / 100.0 * height))
        rows.append([px, py])
    if not rows:
        return np.zeros((0, 2), dtype=np.int32)
    return np.asarray(rows, dtype=np.int32)


def pixels_to_percent_points(
    pixels: np.ndarray,
    *,
    width: int,
    height: int,
) -> list[list[float]]:
    """Convert pixel coordinates to LS percent ``[[x, y], ...]``."""

    if width <= 0 or height <= 0:
        raise ValueError(
            f"width/height must be > 0, got width={width!r}, height={height!r}"
        )
    arr = np.asarray(pixels, dtype=np.float64).reshape(-1, 2)
    out: list[list[float]] = []
    for x, y in arr:
        out.append([float(x) / width * 100.0, float(y) / height * 100.0])
    return out


def polygons_to_binary_mask(
    polygons_percent: Sequence[Sequence[Sequence[float]]],
    *,
    width: int,
    height: int,
) -> np.ndarray:
    """Rasterize one or more percent polygons with ``cv2.fillPoly`` (OR-union).

    Returns a ``numpy.ndarray`` of shape ``(height, width)``, dtype ``uint8``,
    with foreground ``1`` and background ``0``.
    """

    if width <= 0 or height <= 0:
        raise ValueError(
            f"width/height must be > 0, got width={width!r}, height={height!r}"
        )
    mask = np.zeros((height, width), dtype=np.uint8)
    for index, points in enumerate(polygons_percent):
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
            raise ValueError(
                f"polygons_percent[{index}] must be a sequence of points"
            )
        if len(points) < 3:
            continue
        pts = percent_points_to_pixels(points, width=width, height=height)
        cv2.fillPoly(mask, [pts], 1)
    return mask


def polygon_results_to_binary_mask(
    polygon_entries: Sequence[dict[str, Any]],
    *,
    image_id: str,
) -> np.ndarray:
    """Decode one or more SEG polygonlabels result objects and OR-union them."""

    if not polygon_entries:
        raise ValueError(
            f"no polygon entries to decode (image_id={image_id!r})"
        )

    width: int | None = None
    height: int | None = None
    polygons: list[Sequence[Sequence[float]]] = []

    for index, entry in enumerate(polygon_entries):
        try:
            ow = int(entry["original_width"])
            oh = int(entry["original_height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"polygon entry missing original_width/original_height "
                f"(image_id={image_id!r}, index={index})"
            ) from exc
        if ow <= 0 or oh <= 0:
            raise ValueError(
                f"invalid original size {ow}x{oh} "
                f"(image_id={image_id!r}, index={index})"
            )
        if width is None:
            width, height = ow, oh
        elif (ow, oh) != (width, height):
            raise ValueError(
                f"polygon size mismatch: expected {width}x{height}, "
                f"got {ow}x{oh} (image_id={image_id!r}, index={index})"
            )
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"polygon value must be an object "
                f"(image_id={image_id!r}, index={index})"
            )
        points = value.get("points")
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(
                f"polygon value.points must be a list of >= 3 points "
                f"(image_id={image_id!r}, index={index})"
            )
        polygons.append(points)

    assert width is not None and height is not None
    return polygons_to_binary_mask(polygons, width=width, height=height)


def save_uint8_mask_png(path: Path | str, mask: np.ndarray) -> Path:
    """Write a uint8 binary mask (0/1 or 0/255) as an L-mode PNG (fg=255)."""

    arr = np.asarray(mask)
    if arr.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {arr.shape!r}")
    if arr.size == 0:
        raise ValueError("mask must be non-empty")
    binary = (arr > 0).astype(np.uint8) * 255
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(binary, mode="L")
    img.save(target)
    return target.resolve()


def write_manual_mask_from_polygon_results(
    polygon_entries: Sequence[dict[str, Any]],
    *,
    image_id: str,
    manual_mask_dir: Path | str,
) -> str:
    """Decode polygon results, write ``{image_id}_manual.png``, return mask_ref."""

    binary = polygon_results_to_binary_mask(
        polygon_entries, image_id=image_id
    )
    out_dir = Path(manual_mask_dir)
    out_path = out_dir / manual_mask_filename(image_id)
    save_uint8_mask_png(out_path, binary)
    return manual_mask_ref(image_id)


def load_foreground_mask_numpy(
    path: Path | str,
) -> tuple[np.ndarray, int, int]:
    """Load a mask image as uint8 binary ``(H, W)`` plus ``(width, height)``."""

    path = Path(path)
    try:
        with Image.open(path) as img:
            width, height = img.size
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                rgba = np.asarray(img.convert("RGBA"))
                binary = (rgba[:, :, 3] > 0).astype(np.uint8)
            else:
                gray = np.asarray(img.convert("L"))
                binary = (gray > 0).astype(np.uint8)
    except OSError as exc:
        raise ValueError(f"failed to read mask image: {path}") from exc
    return binary, width, height


def binary_mask_to_polygon_points(
    mask: np.ndarray,
    *,
    epsilon_ratio: float = DEFAULT_APPROX_EPSILON_RATIO,
) -> list[list[list[float]]]:
    """Extract external contours as LS percent polygons (one list per contour).

    Pipeline: connected components → ``findContours`` → ``approxPolyDP`` →
    percentage points. Components / contours with fewer than 3 vertices after
    approximation are skipped.
    """

    if epsilon_ratio < 0:
        raise ValueError(f"epsilon_ratio must be >= 0, got {epsilon_ratio!r}")
    arr = np.asarray(mask)
    if arr.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {arr.shape!r}")
    height, width = arr.shape
    if height == 0 or width == 0:
        return []

    binary = (arr > 0).astype(np.uint8)
    num_labels, labels = cv2.connectedComponents(binary, connectivity=8)
    polygons: list[list[list[float]]] = []

    for label_id in range(1, num_labels):
        component = (labels == label_id).astype(np.uint8)
        contours, _hierarchy = cv2.findContours(
            component,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        for contour in contours:
            if contour is None or len(contour) < 3:
                continue
            peri = float(cv2.arcLength(contour, True))
            epsilon = float(epsilon_ratio) * peri
            approx = cv2.approxPolyDP(contour, epsilon, True)
            if approx is None or len(approx) < 3:
                continue
            pixels = approx.reshape(-1, 2)
            polygons.append(
                pixels_to_percent_points(pixels, width=width, height=height)
            )

    return polygons


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    """Compute foreground IoU between two binary masks."""

    aa = np.asarray(a) > 0
    bb = np.asarray(b) > 0
    if aa.shape != bb.shape:
        raise ValueError(
            f"mask shape mismatch for IoU: {aa.shape} vs {bb.shape}"
        )
    inter = np.logical_and(aa, bb).sum()
    union = np.logical_or(aa, bb).sum()
    if union == 0:
        return 1.0
    return float(inter) / float(union)


def _resolve_mask_path(mask_root: Path | str, mask_ref: str) -> Path:
    root = Path(mask_root).resolve()
    if not root.is_dir():
        raise ValueError(f"mask_root is not a directory: {root}")
    ref = Path(mask_ref)
    if ref.is_absolute():
        raise ValueError(f"mask_ref must be a relative path, got {mask_ref!r}")
    resolved = (root / ref).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"mask_ref escapes mask_root: mask_ref={mask_ref!r}, mask_root={root}"
        ) from exc
    return resolved


def build_seg_polygon_results(
    item: PrelabelItem,
    *,
    mask_root: Path | str,
    image_metadata: ImageMetadata | None = None,
    epsilon_ratio: float = DEFAULT_APPROX_EPSILON_RATIO,
) -> list[dict[str, Any]]:
    """Build LS polygonlabels ``result`` entries for one SEG ``PrelabelItem``."""

    if item.task_type is not TaskType.SEG:
        raise ValueError(
            f"build_seg_polygon_results requires SEG item, "
            f"got {item.task_type.value}"
        )
    if not isinstance(item.payload, SegPrelabelPayload):
        raise ValueError("SEG item payload must be SegPrelabelPayload")

    mask_ref = item.payload.mask_ref
    try:
        path = _resolve_mask_path(mask_root, mask_ref)
    except ValueError as exc:
        raise ValueError(
            f"{exc} (image_id={item.image_id!r}, package_id={item.package_id!r})"
        ) from exc

    if not path.is_file():
        raise ValueError(
            "mask file not found: "
            f"{path} (image_id={item.image_id!r}, package_id={item.package_id!r}, "
            f"mask_ref={mask_ref!r})"
        )

    try:
        binary, width, height = load_foreground_mask_numpy(path)
    except ValueError as exc:
        raise ValueError(
            f"{exc} (image_id={item.image_id!r}, package_id={item.package_id!r}, "
            f"mask_ref={mask_ref!r})"
        ) from exc

    if image_metadata is not None and (
        image_metadata.width != width or image_metadata.height != height
    ):
        raise ValueError(
            "mask size does not match image_metadata: "
            f"mask=({width}, {height}), "
            f"image_metadata=({image_metadata.width}, {image_metadata.height}), "
            f"image_id={item.image_id!r}, package_id={item.package_id!r}"
        )

    polygons = binary_mask_to_polygon_points(
        binary, epsilon_ratio=epsilon_ratio
    )
    if not polygons:
        return []

    # Prefer polygonlabels type for new prefill; fall back if specs still brush.
    spec = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]
    labels = list(spec["labels"])
    result_type = "polygonlabels"
    results: list[dict[str, Any]] = []
    for points in polygons:
        results.append(
            {
                "original_width": width,
                "original_height": height,
                "image_rotation": 0,
                "from_name": spec["from_name"],
                "to_name": spec["to_name"],
                "type": result_type,
                "value": {
                    "points": points,
                    "polygonlabels": labels,
                },
            }
        )
    return results


__all__ = [
    "DEFAULT_APPROX_EPSILON_RATIO",
    "MANUAL_MASK_REL_DIR",
    "binary_mask_to_polygon_points",
    "build_seg_polygon_results",
    "load_foreground_mask_numpy",
    "mask_iou",
    "manual_mask_filename",
    "manual_mask_ref",
    "percent_points_to_pixels",
    "pixels_to_percent_points",
    "polygon_results_to_binary_mask",
    "polygons_to_binary_mask",
    "save_uint8_mask_png",
    "write_manual_mask_from_polygon_results",
]
