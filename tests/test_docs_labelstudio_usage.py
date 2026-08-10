"""Smoke tests for Label Studio usage documentation (T3.5)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC = _REPO_ROOT / "docs" / "labelstudio_usage.md"


def test_labelstudio_usage_doc_exists() -> None:
    assert _DOC.is_file()
    text = _DOC.read_text(encoding="utf-8")
    assert text.strip()


def test_labelstudio_usage_doc_covers_required_topics() -> None:
    text = _DOC.read_text(encoding="utf-8")
    required = (
        "mma ls-import",
        "local-files",
        "seg.xml",
        "det.xml",
        "cap.xml",
        "human_confirmed",
        "needs_rework",
        "ls_export",
        "tasks.json",
    )
    for needle in required:
        assert needle in text, f"missing topic marker: {needle}"
