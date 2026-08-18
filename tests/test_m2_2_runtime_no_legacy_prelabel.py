"""M2.2: V1 runtime import graph must not load ``legacy_prelabel``."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PREVIOUS_ANNOTATIONS_SRC = (
    _REPO_ROOT / "src" / "mma" / "exporters" / "previous_annotations.py"
)

_PROBE = """
import sys

import mma.importers.build_ls_tasks
import mma.exporters.parse_ls_export
import mma.exporters.previous_annotations
import mma.exporters.effective_result

loaded = [
    name
    for name in sys.modules
    if name == "mma.formats.legacy_prelabel"
    or name.startswith("mma.formats.legacy_prelabel.")
]
assert not loaded, loaded
"""


def test_previous_annotations_source_has_no_legacy_prelabel_types() -> None:
    text = _PREVIOUS_ANNOTATIONS_SRC.read_text(encoding="utf-8")
    for needle in ("legacy_prelabel", "PrelabelItem", "PrelabelBBox"):
        assert needle not in text, needle


def test_v1_runtime_imports_do_not_load_legacy_prelabel() -> None:
    env = os.environ.copy()
    src = str(_REPO_ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src if not existing else src + os.pathsep + existing
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"legacy_prelabel leaked into V1 import graph:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
