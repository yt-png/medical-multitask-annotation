"""R3: V1 rework prefill must not use LS export raw side-channel."""

from __future__ import annotations

from pathlib import Path

import pytest

from mma.common.models import TaskType
from mma.importers.build_rework_tasks import build_rework_ls_tasks
from mma.importers import rework_import_from_export as rework_glue

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BUILD_REWORK = (
    _REPO_ROOT / "src" / "mma" / "importers" / "build_rework_tasks.py"
)
_REWORK_GLUE = (
    _REPO_ROOT / "src" / "mma" / "importers" / "rework_import_from_export.py"
)

_FORBIDDEN_TOKENS = (
    "_build_from_export",
    "prediction_source",
    "raw_results_by_image_id",
)


def test_importer_sources_have_no_raw_prefill_api() -> None:
    for path in (_BUILD_REWORK, _REWORK_GLUE):
        text = path.read_text(encoding="utf-8")
        for needle in _FORBIDDEN_TOKENS:
            assert needle not in text, f"{path.name} still contains {needle!r}"


def test_build_from_export_is_not_defined() -> None:
    assert not hasattr(rework_glue, "_build_from_export")


def test_prediction_source_kwarg_rejected() -> None:
    with pytest.raises(TypeError):
        build_rework_ls_tasks(
            (),
            batch_id="any_batch",
            task_type=TaskType.CAP,
            prediction_source="raw",
        )


def test_raw_results_kwarg_rejected() -> None:
    with pytest.raises(TypeError):
        build_rework_ls_tasks(
            (),
            batch_id="any_batch",
            task_type=TaskType.CAP,
            raw_results_by_image_id={},
        )
