"""Smoke test for P4 current demo script (uses data/ls_export fake exports)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "examples" / "scripts" / "run_p4_current_demo.py"
_DATA_ROOT = _REPO_ROOT / "data"
_LS_EXPORT = _DATA_ROOT / "ls_export" / "demo_batch"
_RESULTS = _DATA_ROOT / "results" / "demo_batch"

_REQUIRED_EXPORTS = (
    _LS_EXPORT / "seg" / "project-14-at-2026-08-11-10-30-fda1a4bc.json",
    _LS_EXPORT / "det" / "project-15-at-2026-08-11-10-31-dada240b.json",
    _LS_EXPORT / "cap" / "project-16-at-2026-08-11-10-33-a94520f3.json",
)


@pytest.mark.skipif(
    not all(path.is_file() for path in _REQUIRED_EXPORTS),
    reason="demo_batch LS export JSON not present under data/ls_export",
)
def test_p4_current_demo_writes_three_nonempty_annotation_files() -> None:
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--data-root", str(_DATA_ROOT)],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        f"demo script failed:\nstdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )

    for task in ("seg", "det", "cap"):
        path = _RESULTS / task / "current" / "annotations.json"
        assert path.is_file(), f"missing current file: {path}"
        text = path.read_text(encoding="utf-8").strip()
        assert text, f"current file is empty: {path}"
        payload = json.loads(text)
        assert isinstance(payload, list), f"expected JSON array: {path}"
        assert payload, f"expected non-empty items: {path}"
        assert "image_id" in payload[0]
        assert "annotation" in payload[0]
        assert "human_confirmed" in payload[0]
        assert "needs_rework" in payload[0]
