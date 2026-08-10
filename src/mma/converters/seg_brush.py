"""SEG mask → Label Studio brush predictions (T3.1b).

Reads a single ``mask_ref`` file, splits 8-connected foreground components,
and encodes each as LS-compatible brush RLE. Does not change the P2
``SegPrelabelPayload`` contract (one mask file per image).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image

from mma.common.models import TaskType
from mma.converters.to_labelstudio import (
    DEFAULT_LS_RESULT_SPECS,
    ImageMetadata,
)
from mma.formats.intermediate import PrelabelItem, SegPrelabelPayload

# Foreground intensity written into LS RLE channel payload (matches LS converter).
_FOREGROUND_VALUE = 255


def _bits2byte(arr_str: str, n: int = 8) -> list[int]:
    rle: list[int] = []
    numbers = [arr_str[i : i + n] for i in range(0, len(arr_str), n)]
    for chunk in numbers:
        rle.append(int(chunk, 2))
    return rle


def _base_rle_encode(values: list[int]) -> tuple[list[int], list[int], list[int]]:
    """Return (run_lengths, start_positions, run_values) for a 1-D sequence."""

    n = len(values)
    if n == 0:
        return [], [], []

    lengths: list[int] = []
    positions: list[int] = []
    run_values: list[int] = []
    start = 0
    for i in range(1, n):
        if values[i] != values[i - 1]:
            lengths.append(i - start)
            positions.append(start)
            run_values.append(values[i - 1])
            start = i
    lengths.append(n - start)
    positions.append(start)
    run_values.append(values[start])
    return lengths, positions, run_values


def encode_rle(
    arr: list[int],
    *,
    wordsize: int = 8,
    rle_sizes: tuple[int, int, int, int] = (3, 4, 8, 16),
) -> list[int]:
    """Encode a flat channel array to Label Studio brush RLE (pure Python).

    Semantics align with ``label_studio_converter.brush.encode_rle``.
    """

    num = len(arr)
    numbits = f"{num:032b}"
    wordsizebits = f"{wordsize - 1:05b}"
    rle_bits = "".join(f"{x - 1:04b}" for x in rle_sizes)
    base_str = numbits + wordsizebits + rle_bits

    out_str = ""
    for length_reeks, _pos, value in zip(*_base_rle_encode(arr), strict=True):
        if length_reeks == 1:
            out_str += "0"
            out_str += "00"
            out_str += "000"
            out_str += f"{value:08b}"
        elif length_reeks > 1:
            if length_reeks <= 8:
                out_str += "1"
                out_str += "00"
                out_str += f"{length_reeks - 1:03b}"
                out_str += f"{value:08b}"
            elif 8 < length_reeks <= 16:
                out_str += "1"
                out_str += "01"
                out_str += f"{length_reeks - 1:04b}"
                out_str += f"{value:08b}"
            elif 16 < length_reeks <= 256:
                out_str += "1"
                out_str += "10"
                out_str += f"{length_reeks - 1:08b}"
                out_str += f"{value:08b}"
            else:
                length_temp = length_reeks
                while length_temp > 2**16:
                    out_str += "1"
                    out_str += "11"
                    out_str += f"{2**16 - 1:016b}"
                    out_str += f"{value:08b}"
                    length_temp -= 2**16
                out_str += "1"
                out_str += "11"
                out_str += f"{length_temp - 1:016b}"
                out_str += f"{value:08b}"

    total_str = base_str + out_str
    nzfill = (8 - len(total_str) % 8) % 8
    total_str = total_str + ("0" * nzfill)
    return _bits2byte(total_str)


def mask_to_ls_rle(binary_hw: list[list[int]]) -> list[int]:
    """Encode an H×W binary mask (0/1) as Label Studio brush RLE."""

    if not binary_hw or not binary_hw[0]:
        raise ValueError("binary mask must be non-empty")
    flat: list[int] = []
    for row in binary_hw:
        for cell in row:
            v = _FOREGROUND_VALUE if cell else 0
            flat.extend((v, v, v, v))
    return encode_rle(flat)


def load_foreground_mask(path: Path | str) -> tuple[list[list[int]], int, int]:
    """Load a mask image and return (binary H×W, width, height).

    RGBA: alpha > 0 is foreground. Otherwise use L / first channel; pixel > 0
    is foreground.
    """

    path = Path(path)
    try:
        with Image.open(path) as img:
            width, height = img.size
            if img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            ):
                rgba = img.convert("RGBA")
                px = rgba.load()
                binary = [
                    [1 if px[x, y][3] > 0 else 0 for x in range(width)]
                    for y in range(height)
                ]
            else:
                gray = img.convert("L")
                px = gray.load()
                binary = [
                    [1 if px[x, y] > 0 else 0 for x in range(width)]
                    for y in range(height)
                ]
    except OSError as exc:
        raise ValueError(f"failed to read mask image: {path}") from exc

    return binary, width, height


def _neighbors8(y: int, x: int, height: int, width: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                out.append((ny, nx))
    return out


def find_connected_components(
    binary: list[list[int]],
    *,
    connectivity: int = 8,
) -> list[list[list[int]]]:
    """Return 8-connected foreground components as full-size binary masks.

    Components are sorted by centroid ``(cy, cx)`` (row then column).
    Area filtering is not applied (threshold = 0).
    """

    if connectivity != 8:
        raise ValueError("only 8-connectivity is supported")
    if not binary:
        return []
    height = len(binary)
    width = len(binary[0])
    visited = [[False] * width for _ in range(height)]
    components: list[tuple[float, float, list[list[int]]]] = []

    for y in range(height):
        for x in range(width):
            if binary[y][x] == 0 or visited[y][x]:
                continue
            component = [[0] * width for _ in range(height)]
            queue: deque[tuple[int, int]] = deque([(y, x)])
            visited[y][x] = True
            cells: list[tuple[int, int]] = []
            while queue:
                cy, cx = queue.popleft()
                component[cy][cx] = 1
                cells.append((cy, cx))
                for ny, nx in _neighbors8(cy, cx, height, width):
                    if binary[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        queue.append((ny, nx))
            n = len(cells)
            cy = sum(p[0] for p in cells) / n
            cx = sum(p[1] for p in cells) / n
            components.append((cy, cx, component))

    components.sort(key=lambda item: (item[0], item[1]))
    return [comp for _cy, _cx, comp in components]


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


def build_seg_brush_results(
    item: PrelabelItem,
    *,
    mask_root: Path | str,
    image_metadata: ImageMetadata | None = None,
) -> list[dict[str, Any]]:
    """Build LS brush ``result`` entries for one SEG ``PrelabelItem``."""

    if item.task_type is not TaskType.SEG:
        raise ValueError(
            f"build_seg_brush_results requires SEG item, got {item.task_type.value}"
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
        binary, width, height = load_foreground_mask(path)
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

    components = find_connected_components(binary, connectivity=8)
    if not components:
        return []

    spec = DEFAULT_LS_RESULT_SPECS[TaskType.SEG]
    labels = list(spec["labels"])
    results: list[dict[str, Any]] = []
    for component in components:
        rle = mask_to_ls_rle(component)
        results.append(
            {
                "original_width": width,
                "original_height": height,
                "image_rotation": 0,
                "from_name": spec["from_name"],
                "to_name": spec["to_name"],
                "type": spec["type"],
                "value": {
                    "format": "rle",
                    "rle": rle,
                    "brushlabels": labels,
                },
            }
        )
    return results
