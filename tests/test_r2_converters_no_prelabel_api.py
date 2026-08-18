"""R2: V1 converters must not expose prelabel → LS import APIs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONVERTERS_INIT = _REPO_ROOT / "src" / "mma" / "converters" / "__init__.py"
_TO_LABELSTUDIO = _REPO_ROOT / "src" / "mma" / "converters" / "to_labelstudio.py"

_FORBIDDEN_TOKENS = (
    "document_to_ls_tasks",
    "item_to_ls_task",
    "MODEL_VERSION",
    "SEG_PREFILL_MODE",
    "mma-prelabel",
)

_PROBE = """
import sys

import mma.converters
import mma.converters.to_labelstudio
import mma.importers.build_ls_tasks
import mma.exporters.parse_ls_export
import mma.exporters.previous_annotations
import mma.exporters.effective_result

loaded = [
    name
    for name in sys.modules
    if name == "mma.legacy.converters"
    or name.startswith("mma.legacy.converters.")
]
assert not loaded, loaded
"""


def test_v1_converter_sources_have_no_prelabel_ls_api() -> None:
    for path in (_CONVERTERS_INIT, _TO_LABELSTUDIO):
        text = path.read_text(encoding="utf-8")
        for needle in _FORBIDDEN_TOKENS:
            assert needle not in text, f"{path.name} still contains {needle!r}"


def test_package_import_of_prelabel_ls_api_fails() -> None:
    with pytest.raises(ImportError):
        from mma.converters import document_to_ls_tasks  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters import item_to_ls_task  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters import MODEL_VERSION  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters import SEG_PREFILL_MODE  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters import build_seg_polygon_results  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters import build_seg_brush_results  # noqa: F401


def test_submodule_import_of_prelabel_ls_api_fails() -> None:
    with pytest.raises(ImportError):
        from mma.converters.to_labelstudio import document_to_ls_tasks  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters.to_labelstudio import item_to_ls_task  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters.to_labelstudio import MODEL_VERSION  # noqa: F401
    with pytest.raises(ImportError):
        from mma.converters.to_labelstudio import SEG_PREFILL_MODE  # noqa: F401


def test_v1_runtime_imports_do_not_load_legacy_converters() -> None:
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
        f"mma.legacy.converters leaked into V1 import graph:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
