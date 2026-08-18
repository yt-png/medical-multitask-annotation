"""Role CLI helpers for deploy/v1 thin wrappers.

Only resolves and invokes the installed ``mma`` CLI via subprocess.
Does not import MMA business modules.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence

DATA_PROCESSOR_ALLOWED: frozenset[str] = frozenset(
    {
        "preprocess",
        "package",
        "ls-import",
        "export-split",
        "rework-import",
        "merge",
    }
)

ANNOTATOR_ALLOWED: frozenset[str] = frozenset(
    {
        "ls-import",
        "export-split",
        "rework-import",
    }
)

VALID_TASKS: frozenset[str] = frozenset({"seg", "det", "cap"})


class RoleCliError(ValueError):
    """Invalid deploy wrapper usage (command / task allowlist)."""


def resolve_mma_command() -> list[str]:
    """Return argv prefix that invokes the ``mma`` CLI.

    Prefer the ``mma`` console script when on PATH; otherwise
    ``python -m mma``.
    """

    mma_path = shutil.which("mma")
    if mma_path:
        return [mma_path]
    return [sys.executable, "-m", "mma"]


def validate_command(command: str, allowed: frozenset[str]) -> None:
    """Raise RoleCliError if ``command`` is not in the role allowlist."""

    if command not in allowed:
        allowed_s = ", ".join(sorted(allowed))
        raise RoleCliError(
            f"command {command!r} is not allowed for this role; "
            f"allowed: {allowed_s}"
        )


def _collect_task_values(argv: Sequence[str]) -> list[str]:
    """Return every ``--task`` / ``--task=`` value in argv (left to right)."""

    values: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--task":
            if i + 1 >= len(argv):
                raise RoleCliError("--task requires a value")
            values.append(argv[i + 1])
            i += 2
            continue
        if arg.startswith("--task="):
            values.append(arg.split("=", 1)[1])
            i += 1
            continue
        i += 1
    return values


def inject_task(argv: Sequence[str], task: str) -> list[str]:
    """Ensure argv uses the forced ``task``.

    - If ``--task`` is missing, append ``--task <task>``.
    - If a single ``--task`` is present and matches, return a copy of argv.
    - If ``--task`` differs from the forced task, or appears more than once,
      raise RoleCliError (multiple ``--task`` cannot bypass the role lock).
    """

    if task not in VALID_TASKS:
        raise RoleCliError(f"invalid force task {task!r}")

    existing = _collect_task_values(argv)
    if len(existing) > 1:
        raise RoleCliError(
            f"multiple --task values are not allowed; got {existing!r}"
        )
    if not existing:
        return [*argv, "--task", task]
    if existing[0] != task:
        raise RoleCliError(
            f"--task must be {task!r} for this role; got {existing[0]!r}"
        )
    return list(argv)


def build_mma_command(
    command: str,
    argv: Sequence[str],
    *,
    allowed: frozenset[str],
    force_task: str | None = None,
    mma_prefix: Sequence[str] | None = None,
) -> list[str]:
    """Build full subprocess argv for ``mma <command> ...``.

    Parameters
    ----------
    command:
        MMA subcommand (e.g. ``ls-import``).
    argv:
        Extra args after the subcommand (typically ``sys.argv[1:]``).
    allowed:
        Role command allowlist.
    force_task:
        When set, inject / validate ``--task``.
    mma_prefix:
        Optional override for tests; default from :func:`resolve_mma_command`.
    """

    validate_command(command, allowed)
    extra = list(argv)
    if force_task is not None:
        extra = inject_task(extra, force_task)
    prefix = list(mma_prefix) if mma_prefix is not None else resolve_mma_command()
    return [*prefix, command, *extra]


def run_mma(
    command: str,
    argv: Sequence[str] | None = None,
    *,
    allowed: frozenset[str],
    force_task: str | None = None,
) -> int:
    """Validate, build, and run ``mma``; return process exit code."""

    try:
        cmd = build_mma_command(
            command,
            argv if argv is not None else [],
            allowed=allowed,
            force_task=force_task,
        )
    except RoleCliError as exc:
        print(f"deploy: {exc}", file=sys.stderr)
        return 2
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)
