#!/usr/bin/env python3
"""One-shot UAT fixture prep: demo_batch → uat_demo_001 under examples/.

Copies raw images + Excel and rewrites prelabels (batch/package/image ids),
adds a third prelabel item, and synthesizes valid single-channel SEG masks
(sized to match the paired jpg). Does not copy empty placeholder masks.

Does not modify ``examples/*/demo_batch`` or any ``src/mma`` code.
Not part of the production CLI.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_BATCH = "demo_batch"
_DST_BATCH = "uat_demo_001"

_RAW_SRC = _REPO_ROOT / "examples" / "raw" / _SRC_BATCH
_RAW_DST = _REPO_ROOT / "examples" / "raw" / _DST_BATCH
_PRE_SRC = _REPO_ROOT / "examples" / "prelabels" / _SRC_BATCH
_PRE_DST = _REPO_ROOT / "examples" / "prelabels" / _DST_BATCH

_TASKS = ("seg", "det", "cap")

# image_id sequence N ↔ raw jpg img_{N:03d}.jpg (same order as demo Excel).
_SEQ_TO_JPG = {1: "img_001.jpg", 2: "img_002.jpg", 3: "img_003.jpg"}

# Third-item payload templates (diagnosis aligned with demo Excel row C).
_ITEM3_DIAGNOSIS = "假数据诊断 C"
_ITEM3_CAP_CAPTION = "UAT placeholder caption for image 000003."


def _die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _rewrite_ids(text: str) -> str:
    """Replace demo_batch id prefixes with uat_demo_001 (longest-first safe)."""

    return text.replace(_SRC_BATCH, _DST_BATCH)


def _image_id(seq: int) -> str:
    return f"{_DST_BATCH}__{seq:06d}"


def _package_id(task: str) -> str:
    return f"{_DST_BATCH}__{task}"


def _ensure_sources() -> None:
    if not _RAW_SRC.is_dir():
        _die(f"missing raw source: {_RAW_SRC}")
    images = _RAW_SRC / "images"
    excel = _RAW_SRC / "diagnoses.xlsx"
    if not images.is_dir():
        _die(f"missing images dir: {images}")
    for name in _SEQ_TO_JPG.values():
        path = images / name
        if not path.is_file():
            _die(f"missing jpg: {path}")
    if not excel.is_file():
        _die(f"missing excel: {excel}")
    if not _PRE_SRC.is_dir():
        _die(f"missing prelabels source: {_PRE_SRC}")
    for task in _TASKS:
        path = _PRE_SRC / task / "prelabels.json"
        if not path.is_file():
            _die(f"missing prelabels: {path}")


def _refuse_if_exists(*, force: bool) -> None:
    conflicts = [p for p in (_RAW_DST, _PRE_DST) if p.exists()]
    if not conflicts:
        return
    if not force:
        listed = ", ".join(str(p) for p in conflicts)
        _die(
            f"destination already exists ({listed}); "
            "refuse to overwrite demo_batch or existing uat output. "
            "Pass --force to replace uat_demo_001 only."
        )
    for path in conflicts:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _copy_raw() -> None:
    images_src = _RAW_SRC / "images"
    images_dst = _RAW_DST / "images"
    images_dst.mkdir(parents=True, exist_ok=True)
    # Keep all three demo jpgs (img_001..003).
    for jpg in sorted(images_src.glob("*.jpg")):
        shutil.copy2(jpg, images_dst / jpg.name)
    shutil.copy2(_RAW_SRC / "diagnoses.xlsx", _RAW_DST / "diagnoses.xlsx")


def _item3_seg() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "batch_id": _DST_BATCH,
        "package_id": _package_id("seg"),
        "task_type": "SEG",
        "image_id": _image_id(3),
        "diagnosis_text": _ITEM3_DIAGNOSIS,
        "payload": {"mask_ref": f"masks/{_image_id(3)}.png"},
    }


def _item3_det() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "batch_id": _DST_BATCH,
        "package_id": _package_id("det"),
        "task_type": "DET",
        "image_id": _image_id(3),
        "diagnosis_text": _ITEM3_DIAGNOSIS,
        "payload": {"bboxes": []},
    }


def _item3_cap() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "batch_id": _DST_BATCH,
        "package_id": _package_id("cap"),
        "task_type": "CAP",
        "image_id": _image_id(3),
        "diagnosis_text": _ITEM3_DIAGNOSIS,
        "payload": {"caption": _ITEM3_CAP_CAPTION},
    }


def _rewrite_document(raw: dict[str, Any], task: str) -> dict[str, Any]:
    """Deep-replace ids via JSON round-trip string replace, then append item 3."""

    text = json.dumps(raw, ensure_ascii=False, indent=2)
    rewritten = json.loads(_rewrite_ids(text))
    if not isinstance(rewritten, dict):
        _die(f"prelabels/{task}: expected object after rewrite")
    items = rewritten.get("items")
    if not isinstance(items, list):
        _die(f"prelabels/{task}: items must be a list")
    existing_ids = {
        item.get("image_id")
        for item in items
        if isinstance(item, dict)
    }
    third_id = _image_id(3)
    if third_id in existing_ids:
        _die(f"prelabels/{task}: {third_id} already present after rewrite")

    if task == "seg":
        items.append(_item3_seg())
    elif task == "det":
        items.append(_item3_det())
    elif task == "cap":
        items.append(_item3_cap())
    else:
        _die(f"unknown task: {task}")

    rewritten["items"] = items
    rewritten["batch_id"] = _DST_BATCH
    rewritten["package_id"] = _package_id(task)
    return rewritten


def _synthesize_mask(size: tuple[int, int], *, seq: int) -> Image.Image:
    """Build an L-mode mask: background 0, foreground 255, same size as jpg."""

    width, height = size
    if width < 1 or height < 1:
        _die(f"invalid image size for mask seq={seq}: {size}")
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    # Distinct simple blobs per image; clamp to canvas (supports 1x1 demos).
    if width == 1 and height == 1:
        mask.putpixel((0, 0), 255)
        return mask
    # Offset blobs so the three masks are not identical.
    ox = (seq - 1) * max(1, width // 8)
    oy = (seq - 1) * max(1, height // 8)
    x0 = min(max(0, width // 4 + ox), width - 1)
    y0 = min(max(0, height // 4 + oy), height - 1)
    x1 = min(max(x0, (3 * width) // 4 + ox), width - 1)
    y1 = min(max(y0, (3 * height) // 4 + oy), height - 1)
    draw.rectangle([x0, y0, x1, y1], fill=255)
    return mask


def _write_seg_masks() -> list[Path]:
    """Create three valid PNG masks under prelabels/.../seg/masks/."""

    images_dir = _RAW_DST / "images"
    dst_masks = _PRE_DST / "seg" / "masks"
    dst_masks.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for seq, jpg_name in _SEQ_TO_JPG.items():
        jpg_path = images_dir / jpg_name
        with Image.open(jpg_path) as jpg:
            size = jpg.size
        out_path = dst_masks / f"{_image_id(seq)}.png"
        mask = _synthesize_mask(size, seq=seq)
        if mask.mode != "L":
            _die(f"mask mode must be L, got {mask.mode}")
        mask.save(out_path, format="PNG")
        written.append(out_path)
    return written


def _verify_masks(paths: list[Path]) -> None:
    """Fail if any mask cannot be opened/verified by Pillow."""

    for path in paths:
        if path.stat().st_size <= 0:
            _die(f"mask is empty: {path}")
        with Image.open(path) as im:
            im.verify()
        # verify() leaves the image unusable; reopen for mode/size checks.
        with Image.open(path) as im:
            if im.mode != "L":
                _die(f"mask must be single-channel L, got {im.mode}: {path}")
            jpg_name = _SEQ_TO_JPG[int(path.stem.rsplit("__", 1)[-1])]
            with Image.open(_RAW_DST / "images" / jpg_name) as jpg:
                if im.size != jpg.size:
                    _die(
                        f"mask size {im.size} != jpg {jpg.size}: {path}"
                    )
            extrema = im.getextrema()
            if extrema != (0, 255) and extrema != (255, 255):
                # Allow all-foreground tiny masks; reject all-zero.
                if extrema[1] == 0:
                    _die(f"mask has no foreground (all 0): {path}")
        print(f"OK: verified mask {path.relative_to(_REPO_ROOT)}")


def _copy_prelabels() -> None:
    for task in _TASKS:
        src_json = _PRE_SRC / task / "prelabels.json"
        dst_dir = _PRE_DST / task
        dst_dir.mkdir(parents=True, exist_ok=True)
        raw = json.loads(src_json.read_text(encoding="utf-8"))
        doc = _rewrite_document(raw, task)
        out = dst_dir / "prelabels.json"
        out.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # Synthesize masks (do not copy 0-byte placeholders from demo_batch).
    mask_paths = _write_seg_masks()
    _verify_masks(mask_paths)


def _print_layout() -> None:
    print()
    print("Created layout:")
    print()
    print("examples/")
    print("|-- raw/")
    for line in _simple_tree(_RAW_DST, "|   "):
        print(line)
    print("+-- prelabels/")
    for line in _simple_tree(_PRE_DST, "    "):
        print(line)


def _simple_tree(root: Path, prefix: str) -> list[str]:
    """Print a shallow tree for the uat batch directory."""

    lines: list[str] = [f"{prefix}{_DST_BATCH}/"]
    if not root.is_dir():
        return lines

    def walk(directory: Path, pfx: str) -> None:
        entries = sorted(
            directory.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        for index, entry in enumerate(entries):
            last = index == len(entries) - 1
            branch = "+-- " if last else "|-- "
            name = entry.name + ("/" if entry.is_dir() else "")
            lines.append(f"{pfx}{branch}{name}")
            if entry.is_dir():
                walk(entry, pfx + ("    " if last else "|   "))

    walk(root, prefix)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare examples/raw|prelabels/uat_demo_001 from demo_batch "
            "(does not modify demo_batch)."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"replace existing examples/*/ {_DST_BATCH} if present",
    )
    args = parser.parse_args(argv)

    _ensure_sources()
    _refuse_if_exists(force=args.force)
    _copy_raw()
    _copy_prelabels()

    print(f"OK: wrote {_RAW_DST.relative_to(_REPO_ROOT)}")
    print(f"OK: wrote {_PRE_DST.relative_to(_REPO_ROOT)}")
    print(f"OK: source {_SRC_BATCH} left unchanged")
    _print_layout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
