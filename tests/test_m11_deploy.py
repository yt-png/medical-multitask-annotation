"""M11 deploy/v1 four-role package structure and role_cli tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_V1 = REPO_ROOT / "deploy" / "v1"
SRC_CONFIGS = REPO_ROOT / "src" / "mma" / "labelstudio" / "configs"

# Import deploy helpers without installing deploy as a package.
if str(DEPLOY_V1) not in sys.path:
    sys.path.insert(0, str(DEPLOY_V1))

from _lib.role_cli import (  # noqa: E402
    ANNOTATOR_ALLOWED,
    DATA_PROCESSOR_ALLOWED,
    RoleCliError,
    build_mma_command,
    inject_task,
    validate_command,
)

FORBIDDEN_PATH_TOKENS = ("prelabels", "prediction", "legacy", "adapter")
ANNOTATOR_FORBIDDEN_SCRIPTS = ("preprocess", "package", "merge")
ROLES = ("data_processor", "annotator_seg", "annotator_det", "annotator_cap")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def test_deploy_v1_directories_exist() -> None:
    assert DEPLOY_V1.is_dir()
    assert (DEPLOY_V1 / "README.md").is_file()
    assert (DEPLOY_V1 / "manifest.json").is_file()
    assert (DEPLOY_V1 / "_lib" / "role_cli.py").is_file()
    for role in ROLES:
        assert (DEPLOY_V1 / role).is_dir(), role
        assert (DEPLOY_V1 / role / "README.md").is_file(), role


def test_data_processor_six_entrypoints() -> None:
    bin_dir = DEPLOY_V1 / "data_processor" / "bin"
    expected = {
        "preprocess.py",
        "package.py",
        "ls_import.py",
        "export_split.py",
        "rework_import.py",
        "merge.py",
    }
    names = {p.name for p in bin_dir.glob("*.py")}
    assert expected <= names


def test_annotator_three_entrypoints_each() -> None:
    expected = {"ls_import.py", "export_split.py", "rework_import.py"}
    for role, xml in (
        ("annotator_seg", "seg.xml"),
        ("annotator_det", "det.xml"),
        ("annotator_cap", "cap.xml"),
    ):
        bin_dir = DEPLOY_V1 / role / "bin"
        names = {p.name for p in bin_dir.glob("*.py")}
        assert expected <= names, role
        assert (DEPLOY_V1 / role / "configs" / xml).is_file(), role


def test_forbidden_tokens_not_in_deploy_tree() -> None:
    """Path segments and filenames must not introduce banned concepts."""

    for path in DEPLOY_V1.rglob("*"):
        rel = path.relative_to(DEPLOY_V1).as_posix().lower()
        parts = rel.split("/")
        for token in FORBIDDEN_PATH_TOKENS:
            assert token not in parts, f"{token} in path {rel}"
            assert token not in path.stem.lower(), f"{token} in name {path.name}"


def test_annotator_packages_forbid_processor_scripts() -> None:
    for role in ("annotator_seg", "annotator_det", "annotator_cap"):
        bin_dir = DEPLOY_V1 / role / "bin"
        names = {p.stem.lower() for p in bin_dir.glob("*.py")}
        for banned in ANNOTATOR_FORBIDDEN_SCRIPTS:
            assert banned not in names, f"{role} has {banned}"


def test_annotator_configs_match_src_normalized() -> None:
    pairs = (
        ("seg.xml", DEPLOY_V1 / "annotator_seg" / "configs" / "seg.xml"),
        ("det.xml", DEPLOY_V1 / "annotator_det" / "configs" / "det.xml"),
        ("cap.xml", DEPLOY_V1 / "annotator_cap" / "configs" / "cap.xml"),
    )
    for name, deploy_path in pairs:
        src_text = _normalize_newlines(
            (SRC_CONFIGS / name).read_text(encoding="utf-8")
        )
        deploy_text = _normalize_newlines(deploy_path.read_text(encoding="utf-8"))
        assert deploy_text == src_text, name


def test_manifest_json() -> None:
    data = json.loads((DEPLOY_V1 / "manifest.json").read_text(encoding="utf-8"))
    assert data["sprint"] == "D"
    assert data["milestones"] == ["M11.1", "M11.2", "M11.3", "M11.4", "M11.5"]
    assert data["roles"] == list(ROLES)


def test_role_cli_seg_allows_annotator_commands() -> None:
    for cmd in ("ls-import", "export-split", "rework-import"):
        validate_command(cmd, ANNOTATOR_ALLOWED)
        built = build_mma_command(
            cmd,
            ["--batch", "b1"],
            allowed=ANNOTATOR_ALLOWED,
            force_task="seg",
            mma_prefix=["mma"],
        )
        assert built[:2] == ["mma", cmd]
        assert "--task" in built
        assert built[built.index("--task") + 1] == "seg"


def test_role_cli_seg_rejects_merge_and_package() -> None:
    for cmd in ("merge", "package", "preprocess"):
        with pytest.raises(RoleCliError):
            validate_command(cmd, ANNOTATOR_ALLOWED)
        with pytest.raises(RoleCliError):
            build_mma_command(
                cmd,
                [],
                allowed=ANNOTATOR_ALLOWED,
                force_task="seg",
                mma_prefix=["mma"],
            )


def test_role_cli_wrong_task_fails() -> None:
    with pytest.raises(RoleCliError):
        inject_task(["--task", "det"], "seg")
    with pytest.raises(RoleCliError):
        build_mma_command(
            "ls-import",
            ["--batch", "b", "--task", "det"],
            allowed=ANNOTATOR_ALLOWED,
            force_task="seg",
            mma_prefix=["mma"],
        )


def test_role_cli_multiple_task_flags_fail() -> None:
    """Multiple --task must not bypass the role lock (first-match hole)."""

    with pytest.raises(RoleCliError, match="multiple --task"):
        inject_task(["--task", "seg", "--task", "det"], "seg")
    with pytest.raises(RoleCliError, match="multiple --task"):
        inject_task(["--task=seg", "--task=det"], "seg")
    with pytest.raises(RoleCliError, match="multiple --task"):
        build_mma_command(
            "ls-import",
            ["--batch", "b", "--task", "seg", "--task", "det"],
            allowed=ANNOTATOR_ALLOWED,
            force_task="seg",
            mma_prefix=["mma"],
        )


def test_role_cli_injects_task_when_missing() -> None:
    out = inject_task(["--batch", "b"], "cap")
    assert out == ["--batch", "b", "--task", "cap"]


def test_deploy_tree_has_no_tracked_pycache() -> None:
    """Bytecode may appear after importing role_cli; it must not be git-tracked."""

    import subprocess

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in gitignore
    assert "*.pyc" in gitignore or "*.py[cod]" in gitignore

    listed = subprocess.run(
        ["git", "ls-files", "--", "deploy/v1"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    offenders = [
        p
        for p in listed
        if "__pycache__" in p.replace("\\", "/") or p.endswith(".pyc")
    ]
    assert offenders == [], offenders


def test_role_cli_source_has_no_mma_business_imports() -> None:
    text = (DEPLOY_V1 / "_lib" / "role_cli.py").read_text(encoding="utf-8")
    assert "import mma" not in text
    assert "from mma" not in text
    assert "legacy" not in text.lower()
    assert "adapter" not in text.lower()


def test_data_processor_allowlist_includes_six() -> None:
    for cmd in (
        "preprocess",
        "package",
        "ls-import",
        "export-split",
        "rework-import",
        "merge",
    ):
        validate_command(cmd, DATA_PROCESSOR_ALLOWED)
