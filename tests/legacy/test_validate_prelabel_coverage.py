"""Legacy tests for prelabel coverage helper.

Not part of the V1 runtime test suite; run with ``pytest -m legacy``.
"""

from __future__ import annotations

import pytest

from mma.legacy.validate_prelabel_coverage import validate_prelabel_coverage

pytestmark = pytest.mark.legacy


def test_validate_prelabel_coverage_set_equality() -> None:
    validate_prelabel_coverage(["a", "b", "c"], ["a", "b", "c"])
    with pytest.raises(ValueError, match="Missing prelabels"):
        validate_prelabel_coverage(["a", "b", "c"], ["a", "b"])
    with pytest.raises(ValueError, match="Unknown prelabels"):
        validate_prelabel_coverage(["a", "b"], ["a", "b", "c"])
    validate_prelabel_coverage(["a", "b", "c"], ["c", "a", "b"])
