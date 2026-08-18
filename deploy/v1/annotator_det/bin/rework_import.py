#!/usr/bin/env python3
"""DET annotator wrapper: mma rework-import (--task det forced)."""

from __future__ import annotations

import sys
from pathlib import Path

_V1 = Path(__file__).resolve().parents[2]
if str(_V1) not in sys.path:
    sys.path.insert(0, str(_V1))

from _lib.role_cli import ANNOTATOR_ALLOWED, run_mma  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return run_mma(
        "rework-import",
        sys.argv[1:] if argv is None else argv,
        allowed=ANNOTATOR_ALLOWED,
        force_task="det",
    )


if __name__ == "__main__":
    raise SystemExit(main())
