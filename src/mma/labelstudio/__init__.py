"""Label Studio workbench configs and helpers (P3 / M6)."""

from __future__ import annotations

from pathlib import Path

SEG_CONFIG_NAME = "seg.xml"
DET_CONFIG_NAME = "det.xml"


def seg_config_path() -> Path:
    """Return the filesystem path to the packaged SEG labeling config XML.

    Resolves ``configs/seg.xml`` next to this package (works for editable and
    wheel installs when XML is included via package-data).

    Raises:
        FileNotFoundError: If ``seg.xml`` is missing.
    """

    path = Path(__file__).resolve().parent / "configs" / SEG_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"packaged Label Studio SEG config not found: {path}"
        )
    return path


def load_seg_config_text() -> str:
    """Return the SEG labeling config XML text from package data."""

    return seg_config_path().read_text(encoding="utf-8")


def det_config_path() -> Path:
    """Return the filesystem path to the packaged DET labeling config XML.

    Resolves ``configs/det.xml`` next to this package (works for editable and
    wheel installs when XML is included via package-data).

    Raises:
        FileNotFoundError: If ``det.xml`` is missing.
    """

    path = Path(__file__).resolve().parent / "configs" / DET_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"packaged Label Studio DET config not found: {path}"
        )
    return path


def load_det_config_text() -> str:
    """Return the DET labeling config XML text from package data."""

    return det_config_path().read_text(encoding="utf-8")


__all__ = [
    "DET_CONFIG_NAME",
    "SEG_CONFIG_NAME",
    "det_config_path",
    "load_det_config_text",
    "load_seg_config_text",
    "seg_config_path",
]
