"""Label Studio workbench configs and helpers (P3 / M6)."""

from __future__ import annotations

from pathlib import Path

SEG_CONFIG_NAME = "seg.xml"
DET_CONFIG_NAME = "det.xml"
CAP_CONFIG_NAME = "cap.xml"


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


def cap_config_path() -> Path:
    """Return the filesystem path to the packaged CAP labeling config XML.

    Resolves ``configs/cap.xml`` next to this package (works for editable and
    wheel installs when XML is included via package-data).

    Raises:
        FileNotFoundError: If ``cap.xml`` is missing.
    """

    path = Path(__file__).resolve().parent / "configs" / CAP_CONFIG_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"packaged Label Studio CAP config not found: {path}"
        )
    return path


def load_cap_config_text() -> str:
    """Return the CAP labeling config XML text from package data."""

    return cap_config_path().read_text(encoding="utf-8")


__all__ = [
    "CAP_CONFIG_NAME",
    "DET_CONFIG_NAME",
    "SEG_CONFIG_NAME",
    "cap_config_path",
    "det_config_path",
    "load_cap_config_text",
    "load_det_config_text",
    "load_seg_config_text",
    "seg_config_path",
]
