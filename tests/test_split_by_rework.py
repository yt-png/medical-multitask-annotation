"""Tests for normal/rework split (T4.2)."""

from __future__ import annotations

import pytest

from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.exporters import split_by_rework


def _seg(
    image_id: str,
    *,
    needs_rework: bool,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref=f"masks/{image_id}.png"),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def _det(
    image_id: str,
    *,
    needs_rework: bool,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def _cap(
    image_id: str,
    *,
    needs_rework: bool,
    human_confirmed: bool = True,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=f"caption-{image_id}"),
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    )


def test_empty_input() -> None:
    normal, rework = split_by_rework(())
    assert normal == ()
    assert rework == ()


def test_case1_confirmed_no_rework_goes_normal() -> None:
    items = (_seg("a", needs_rework=False, human_confirmed=True),)
    normal, rework = split_by_rework(items)
    assert [x.image_id for x in normal] == ["a"]
    assert rework == ()


def test_case2_confirmed_rework_goes_rework() -> None:
    items = (_cap("a", needs_rework=True, human_confirmed=True),)
    normal, rework = split_by_rework(items)
    assert normal == ()
    assert [x.image_id for x in rework] == ["a"]


def test_case3_unconfirmed_no_rework_goes_rework() -> None:
    items = (_seg("a", needs_rework=False, human_confirmed=False),)
    normal, rework = split_by_rework(items)
    assert normal == ()
    assert [x.image_id for x in rework] == ["a"]


def test_case4_unconfirmed_rework_flag_goes_rework() -> None:
    items = (_det("a", needs_rework=True, human_confirmed=False),)
    normal, rework = split_by_rework(items)
    assert normal == ()
    assert [x.image_id for x in rework] == ["a"]


def test_all_normal() -> None:
    items = (
        _seg("a", needs_rework=False),
        _seg("b", needs_rework=False),
    )
    normal, rework = split_by_rework(items)
    assert [x.image_id for x in normal] == ["a", "b"]
    assert rework == ()


def test_all_rework() -> None:
    items = (
        _cap("a", needs_rework=True),
        _cap("b", needs_rework=True),
    )
    normal, rework = split_by_rework(items)
    assert normal == ()
    assert [x.image_id for x in rework] == ["a", "b"]


def test_mixed_classification_preserves_order() -> None:
    items = (
        _seg("n1", needs_rework=False),
        _det("r1", needs_rework=True),
        _cap("u1", needs_rework=False, human_confirmed=False),
        _seg("n2", needs_rework=False),
        _seg("r2", needs_rework=True),
        _det("u2", needs_rework=True, human_confirmed=False),
    )
    normal, rework = split_by_rework(items)
    assert [x.image_id for x in normal] == ["n1", "n2"]
    assert [x.image_id for x in rework] == ["r1", "u1", "r2", "u2"]
    assert normal[0] is items[0]
    assert rework[0] is items[1]
    assert rework[1] is items[2]


def test_rejects_non_task_annotation_result() -> None:
    with pytest.raises(TypeError, match="TaskAnnotationResult"):
        split_by_rework([{"image_id": "x", "needs_rework": False}])  # type: ignore[list-item]
