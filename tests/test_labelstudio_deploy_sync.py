"""M9.2: deploy/v1 annotator XML copies match packaged Label Studio configs."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_CONFIGS = REPO_ROOT / "src" / "mma" / "labelstudio" / "configs"
DEPLOY_V1 = REPO_ROOT / "deploy" / "v1"

_PAIRS = (
    ("seg.xml", DEPLOY_V1 / "annotator_seg" / "configs" / "seg.xml"),
    ("det.xml", DEPLOY_V1 / "annotator_det" / "configs" / "det.xml"),
    ("cap.xml", DEPLOY_V1 / "annotator_cap" / "configs" / "cap.xml"),
)


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def test_deploy_annotator_xml_matches_src_normalized() -> None:
    for name, deploy_path in _PAIRS:
        src_path = SRC_CONFIGS / name
        assert src_path.is_file(), src_path
        assert deploy_path.is_file(), deploy_path
        src_text = _normalize(src_path.read_text(encoding="utf-8"))
        deploy_text = _normalize(deploy_path.read_text(encoding="utf-8"))
        assert deploy_text == src_text, name
