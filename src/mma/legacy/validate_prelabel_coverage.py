"""LEGACY: prelabel vs task-package image_id coverage checks.

Historical helper for ``prelabels.json`` vs task-package ``image_id`` sets.
V1 first-round ``ls-import`` does not call this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def validate_prelabel_coverage(
    package_ids: Iterable[str],
    prelabel_ids: Iterable[str],
) -> None:
    """Require package and prelabel ``image_id`` sets to be identical.

    Raises ``ValueError`` listing missing and/or unknown ids. Does not mutate
    either side (no skip / auto-fill / auto-delete).
    """

    package_set = {str(x).strip() for x in package_ids if str(x).strip()}
    prelabel_set = {str(x).strip() for x in prelabel_ids if str(x).strip()}

    missing = sorted(package_set - prelabel_set)
    unknown = sorted(prelabel_set - package_set)
    if not missing and not unknown:
        return

    parts: list[str] = []
    if missing:
        parts.append("Missing prelabels:\n    " + "\n    ".join(missing))
    if unknown:
        parts.append("Unknown prelabels:\n    " + "\n    ".join(unknown))
    raise ValueError(
        "prelabel coverage mismatch (package image_id set must equal "
        "prelabels.json image_id set);\n" + "\n".join(parts)
    )


def format_id_set(ids: Sequence[str]) -> str:
    """Join ids for diagnostics (kept for callers/tests)."""

    return ", ".join(ids)
