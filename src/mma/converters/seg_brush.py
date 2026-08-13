"""SEG mask ↔ Label Studio brush RLE (T3.1b + export persist).

Encode: mask file → LS brush predictions (import prefill).
Decode: LS brush RLE → binary mask / PNG (export → current/final).
Does not change the P2 ``SegPrelabelPayload`` contract (one mask file per image).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
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

# Relative mask_ref under ``results/<batch>/seg/`` for human-confirmed masks.
MANUAL_MASK_REL_DIR = "manual_masks"
MANUAL_MASK_SUFFIX = "_manual.png"


def _bits2byte(arr_str: str, n: int = 8) -> list[int]:
    rle: list[int] = []
    numbers = [arr_str[i : i + n] for i in range(0, len(arr_str), n)]
    for chunk in numbers:
        rle.append(int(chunk, 2))
    return rle


def _access_bit(data: Sequence[int], num: int) -> int:
    base = num // 8
    shift = 7 - (num % 8)
    return (data[base] & (1 << shift)) >> shift


def _bytes2bit(data: Sequence[int]) -> str:
    return "".join(str(_access_bit(data, i)) for i in range(len(data) * 8))


class _BitInputStream:
    """Bit reader for Label Studio brush RLE (pure Python)."""

    def __init__(self, bit_string: str) -> None:
        self._data = bit_string
        self._i = 0

    def read(self, size: int) -> int:
        if size < 0:
            raise ValueError("bit read size must be >= 0")
        if self._i + size > len(self._data):
            raise ValueError("RLE bitstream exhausted while decoding")
        out = self._data[self._i : self._i + size]
        self._i += size
        return int(out, 2) if size else 0


def decode_rle(rle: Sequence[int]) -> list[int]:
    """Decode Label Studio brush RLE to a flat channel array (pure Python).

    Semantics align with ``label_studio_converter.brush.decode_rle`` (no numpy).
    """

    if not isinstance(rle, Sequence) or isinstance(rle, (str, bytes)):
        raise ValueError("rle must be a sequence of ints")
    values = [int(v) for v in rle]
    stream = _BitInputStream(_bytes2bit(values))
    num = stream.read(32)
    word_size = stream.read(5) + 1
    rle_sizes = [stream.read(4) + 1 for _ in range(4)]
    if num < 0:
        raise ValueError(f"invalid RLE length header: {num}")

    out = [0] * num
    i = 0
    while i < num:
        is_run = stream.read(1)
        size_idx = stream.read(2)
        if size_idx >= len(rle_sizes):
            raise ValueError(f"invalid RLE size index: {size_idx}")
        j = i + 1 + stream.read(rle_sizes[size_idx])
        if j > num:
            raise ValueError(
                f"RLE run overflows buffer: i={i}, j={j}, num={num}"
            )
        if is_run:
            val = stream.read(word_size)
            for k in range(i, j):
                out[k] = val
            i = j
        else:
            while i < j:
                out[i] = stream.read(word_size)
                i += 1
    return out


def ls_rle_to_binary_mask(
    rle: Sequence[int],
    *,
    width: int,
    height: int,
) -> list[list[int]]:
    """Decode LS brush RLE to an H×W binary mask (1 = foreground).

    Flat RLE expands to ``height * width * 4`` channels (RGBA); foreground is
    taken from the alpha channel (index 3), matching LS converter practice.
    """

    if width <= 0 or height <= 0:
        raise ValueError(
            f"width/height must be > 0, got width={width!r}, height={height!r}"
        )
    flat = decode_rle(rle)
    expected = height * width * 4
    if len(flat) != expected:
        raise ValueError(
            f"decoded RLE length {len(flat)} != height*width*4 ({expected}) "
            f"(width={width}, height={height})"
        )
    binary: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            alpha = flat[(y * width + x) * 4 + 3]
            row.append(1 if alpha > 0 else 0)
        binary.append(row)
    return binary


def union_binary_masks(
    masks: Sequence[list[list[int]]],
) -> list[list[int]]:
    """OR-union multiple H×W binary masks (same size required)."""

    if not masks:
        raise ValueError("masks must be non-empty")
    height = len(masks[0])
    if height == 0 or not masks[0][0]:
        raise ValueError("masks must be non-empty 2-D")
    width = len(masks[0][0])
    for index, mask in enumerate(masks):
        if len(mask) != height or any(len(row) != width for row in mask):
            raise ValueError(
                f"mask size mismatch at index {index}: "
                f"expected ({height}, {width})"
            )
    out = [[0] * width for _ in range(height)]
    for mask in masks:
        for y in range(height):
            for x in range(width):
                if mask[y][x]:
                    out[y][x] = 1
    return out


def save_binary_mask_png(path: Path | str, binary_hw: list[list[int]]) -> Path:
    """Write an H×W binary mask as an L-mode PNG (fg=255, bg=0)."""

    if not binary_hw or not binary_hw[0]:
        raise ValueError("binary mask must be non-empty")
    height = len(binary_hw)
    width = len(binary_hw[0])
    if any(len(row) != width for row in binary_hw):
        raise ValueError("binary mask rows must share the same width")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("L", (width, height))
    img.putdata([255 if cell else 0 for row in binary_hw for cell in row])
    img.save(target)
    return target.resolve()


def manual_mask_filename(image_id: str) -> str:
    """Return ``{image_id}_manual.png`` (no directory)."""

    cleaned = str(image_id).strip()
    if not cleaned:
        raise ValueError("image_id must be non-empty")
    return f"{cleaned}{MANUAL_MASK_SUFFIX}"


def manual_mask_ref(image_id: str) -> str:
    """Return relative mask_ref ``manual_masks/{image_id}_manual.png``."""

    return f"{MANUAL_MASK_REL_DIR}/{manual_mask_filename(image_id)}"


def brush_results_to_binary_mask(
    brush_entries: Sequence[dict[str, Any]],
    *,
    image_id: str,
) -> list[list[int]]:
    """Decode one or more SEG brush result objects and OR-union them."""

    if not brush_entries:
        raise ValueError(
            f"no brush entries to decode (image_id={image_id!r})"
        )
    masks: list[list[list[int]]] = []
    width: int | None = None
    height: int | None = None
    for index, entry in enumerate(brush_entries):
        try:
            ow = int(entry["original_width"])
            oh = int(entry["original_height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"brush entry missing original_width/original_height "
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
                f"brush size mismatch: expected {width}x{height}, "
                f"got {ow}x{oh} (image_id={image_id!r}, index={index})"
            )
        value = entry.get("value")
        if not isinstance(value, dict):
            raise ValueError(
                f"brush value must be an object "
                f"(image_id={image_id!r}, index={index})"
            )
        rle = value.get("rle")
        if not isinstance(rle, list) or not rle:
            raise ValueError(
                f"brush value.rle must be a non-empty list "
                f"(image_id={image_id!r}, index={index})"
            )
        assert width is not None and height is not None
        masks.append(
            ls_rle_to_binary_mask(rle, width=width, height=height)
        )
    return union_binary_masks(masks)


def write_manual_mask_from_brush_results(
    brush_entries: Sequence[dict[str, Any]],
    *,
    image_id: str,
    manual_mask_dir: Path | str,
) -> str:
    """Decode brush results, write ``{image_id}_manual.png``, return mask_ref."""

    binary = brush_results_to_binary_mask(brush_entries, image_id=image_id)
    out_dir = Path(manual_mask_dir)
    out_path = out_dir / manual_mask_filename(image_id)
    save_binary_mask_png(out_path, binary)
    return manual_mask_ref(image_id)


def write_empty_manual_mask(
    *,
    image_id: str,
    width: int,
    height: int,
    manual_mask_dir: Path | str,
) -> str:
    """Write an all-background manual mask PNG and return ``mask_ref``.

    Used when the annotator cleared every SEG brush region (human empty mask).
    ``width`` / ``height`` must be positive pixel sizes of the source image.
    """

    if width <= 0 or height <= 0:
        raise ValueError(
            f"empty manual mask requires positive width/height "
            f"(image_id={image_id!r}, got {width}x{height})"
        )
    binary = [[0] * width for _ in range(height)]
    out_dir = Path(manual_mask_dir)
    out_path = out_dir / manual_mask_filename(image_id)
    save_binary_mask_png(out_path, binary)
    return manual_mask_ref(image_id)


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
