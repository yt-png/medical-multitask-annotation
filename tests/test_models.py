"""Tests for core data contracts (T0.2). No real image/Excel I/O.

Includes M5.6 lock-in for empty / missing task payload → rework
(``has_effective_task_payload`` / ``should_rework_result`` / ResultBundle).
"""

from __future__ import annotations

import pytest

from mma.common.models import (
    BatchContext,
    BBox,
    BundleKind,
    CapAnnotation,
    DetAnnotation,
    ImageRecord,
    MergedMultitaskRecord,
    ResultBundle,
    SampleItem,
    SegAnnotation,
    TaskAnnotationResult,
    TaskPackage,
    TaskType,
    assert_annotation_matches_task,
)


def test_task_type_values() -> None:
    assert {t.value for t in TaskType} == {"SEG", "DET", "CAP"}


def test_bundle_kind_values() -> None:
    assert {k.value for k in BundleKind} == {"normal", "rework"}


def test_construct_image_record_and_sample() -> None:
    image = ImageRecord(
        image_id="img-001",
        image_path="images/img-001.jpg",
        diagnosis_text="benign nodule",
        batch_id="batch-a",
        source_image_name="raw_001.jpg",
    )
    sample = SampleItem(
        image_id=image.image_id,
        image_path=image.image_path,
        diagnosis_text=image.diagnosis_text,
    )
    assert sample.image_id == "img-001"
    assert image.batch_id == "batch-a"


def test_construct_task_package_allows_empty_samples() -> None:
    package = TaskPackage(
        package_id="pkg-seg-1",
        task_type=TaskType.SEG,
        samples=(),
        batch_id="batch-a",
    )
    assert package.samples == ()
    assert package.task_type is TaskType.SEG


def test_construct_task_package_with_samples() -> None:
    samples = (
        SampleItem("img-1", "a.jpg", "text-a"),
        SampleItem("img-2", "b.jpg", "text-b"),
    )
    package = TaskPackage(
        package_id="pkg-det-1",
        task_type=TaskType.DET,
        samples=samples,
    )
    assert len(package.samples) == 2


def test_construct_annotations_and_results() -> None:
    seg = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="masks/img-1.png"),
        human_confirmed=True,
        needs_rework=False,
    )
    det = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=(BBox(0.1, 0.2, 0.3, 0.4),)),
        human_confirmed=True,
        needs_rework=False,
        package_id="pkg-det-1",
        export_round=1,
    )
    cap = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="left lung opacity"),
        human_confirmed=True,
        needs_rework=True,
    )
    assert isinstance(seg.annotation, SegAnnotation)
    assert det.package_id == "pkg-det-1"
    assert cap.needs_rework is True


def test_should_rework_truth_table() -> None:
    from mma.common.models import should_rework

    # human_confirmed, needs_rework → should_rework / bucket
    assert should_rework(human_confirmed=False, needs_rework=False) is True  # rework
    assert should_rework(human_confirmed=False, needs_rework=True) is True  # rework
    assert should_rework(human_confirmed=True, needs_rework=False) is False  # normal
    assert should_rework(human_confirmed=True, needs_rework=True) is True  # rework


@pytest.mark.parametrize(
    ("human_confirmed", "needs_rework", "bucket"),
    [
        (False, False, "rework"),
        (False, True, "rework"),
        (True, False, "normal"),
        (True, True, "rework"),
    ],
)
def test_should_rework_parametrized_buckets(
    human_confirmed: bool,
    needs_rework: bool,
    bucket: str,
) -> None:
    from mma.common.models import should_rework

    assert should_rework(
        human_confirmed=human_confirmed,
        needs_rework=needs_rework,
    ) is (bucket == "rework")


def test_has_effective_task_payload_det_cap() -> None:
    from mma.common.models import has_effective_task_payload

    assert (
        has_effective_task_payload(
            TaskType.DET,
            DetAnnotation(bboxes=(BBox(0.0, 0.0, 1.0, 1.0),)),
        )
        is True
    )
    assert (
        has_effective_task_payload(TaskType.DET, DetAnnotation(bboxes=()))
        is False
    )
    assert (
        has_effective_task_payload(
            TaskType.CAP, CapAnnotation(caption="left lung")
        )
        is True
    )
    assert (
        has_effective_task_payload(TaskType.CAP, CapAnnotation(caption=""))
        is False
    )
    assert (
        has_effective_task_payload(TaskType.CAP, CapAnnotation(caption="  \n"))
        is False
    )


def test_has_effective_task_payload_seg_has_foreground() -> None:
    """SEG: non-empty mask_ref and has_foreground."""

    from mma.common.models import has_effective_task_payload

    assert (
        has_effective_task_payload(
            TaskType.SEG,
            SegAnnotation(
                mask_ref="manual_masks/x_manual.png", has_foreground=True
            ),
        )
        is True
    )
    assert (
        has_effective_task_payload(
            TaskType.SEG,
            SegAnnotation(
                mask_ref="manual_masks/x_manual.png", has_foreground=False
            ),
        )
        is False
    )
    assert (
        has_effective_task_payload(TaskType.SEG, SegAnnotation(mask_ref=""))
        is False
    )


def test_has_effective_task_payload_seg_whitespace_mask_ref() -> None:
    from mma.common.models import has_effective_task_payload

    assert (
        has_effective_task_payload(TaskType.SEG, SegAnnotation(mask_ref="  "))
        is False
    )


def test_should_rework_result_or_empty_payload() -> None:
    from mma.common.models import should_rework_result

    empty_det = TaskAnnotationResult(
        image_id="img-det",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=True,
        needs_rework=False,
    )
    empty_cap = TaskAnnotationResult(
        image_id="img-cap",
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=""),
        human_confirmed=True,
        needs_rework=False,
    )
    empty_seg = TaskAnnotationResult(
        image_id="img-seg",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(
            mask_ref="manual_masks/img_manual.png", has_foreground=False
        ),
        human_confirmed=True,
        needs_rework=False,
    )
    assert should_rework_result(empty_det) is True
    assert should_rework_result(empty_cap) is True
    assert should_rework_result(empty_seg) is True


def test_should_rework_result_confirmed_with_payload_normal() -> None:
    from mma.common.models import should_rework_result

    item = TaskAnnotationResult(
        image_id="img-ok",
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="ok"),
        human_confirmed=True,
        needs_rework=False,
    )
    assert should_rework_result(item) is False


def test_should_rework_result_override_has_task_payload() -> None:
    from mma.common.models import should_rework_result

    item = TaskAnnotationResult(
        image_id="img-seg",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="manual_masks/img_manual.png"),
        human_confirmed=True,
        needs_rework=False,
    )
    assert should_rework_result(item) is False
    assert should_rework_result(item, has_task_payload=False) is True


def test_should_rework_result_unconfirmed_still_rework() -> None:
    from mma.common.models import should_rework_result

    item = TaskAnnotationResult(
        image_id="img-u",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=(BBox(1.0, 2.0, 3.0, 4.0),)),
        human_confirmed=False,
        needs_rework=False,
    )
    assert should_rework_result(item) is True


def test_construct_result_bundles() -> None:
    normal_item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="m1"),
        human_confirmed=True,
        needs_rework=False,
    )
    rework_item = TaskAnnotationResult(
        image_id="img-2",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="m2"),
        human_confirmed=True,
        needs_rework=True,
    )
    normal = ResultBundle(
        bundle_kind=BundleKind.NORMAL,
        task_type=TaskType.SEG,
        items=(normal_item,),
        batch_id="batch-a",
    )
    rework = ResultBundle(
        bundle_kind=BundleKind.REWORK,
        task_type=TaskType.SEG,
        items=(rework_item,),
    )
    assert normal.bundle_kind is BundleKind.NORMAL
    assert rework.bundle_kind is BundleKind.REWORK


def test_construct_merged_multitask_record() -> None:
    record = MergedMultitaskRecord(
        image_id="img-1",
        seg=SegAnnotation(mask_ref="m1"),
        det=DetAnnotation(bboxes=()),
        cap=CapAnnotation(caption="ok"),
        image_path="a.jpg",
        diagnosis_text="diag",
    )
    assert record.seg.mask_ref == "m1"
    assert record.cap.caption == "ok"


def test_seg_result_rejects_det_annotation() -> None:
    with pytest.raises(ValueError, match="does not match"):
        TaskAnnotationResult(
            image_id="img-1",
            task_type=TaskType.SEG,
            annotation=DetAnnotation(bboxes=()),
            human_confirmed=True,
            needs_rework=False,
        )


def test_det_result_rejects_cap_annotation() -> None:
    with pytest.raises(ValueError, match="does not match"):
        TaskAnnotationResult(
            image_id="img-1",
            task_type=TaskType.DET,
            annotation=CapAnnotation(caption="x"),
            human_confirmed=True,
            needs_rework=False,
        )


def test_cap_result_rejects_seg_annotation() -> None:
    with pytest.raises(ValueError, match="does not match"):
        assert_annotation_matches_task(
            TaskType.CAP,
            SegAnnotation(mask_ref="m"),
        )


def test_normal_bundle_rejects_rework_item() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=True,
        needs_rework=True,
    )
    with pytest.raises(ValueError, match="NORMAL bundle"):
        ResultBundle(
            bundle_kind=BundleKind.NORMAL,
            task_type=TaskType.DET,
            items=(item,),
        )


def test_rework_bundle_rejects_normal_item() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=(BBox(1.0, 2.0, 3.0, 4.0),)),
        human_confirmed=True,
        needs_rework=False,
    )
    with pytest.raises(ValueError, match="REWORK bundle"):
        ResultBundle(
            bundle_kind=BundleKind.REWORK,
            task_type=TaskType.DET,
            items=(item,),
        )


def test_normal_bundle_rejects_empty_payload_item() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=True,
        needs_rework=False,
    )
    with pytest.raises(ValueError, match="NORMAL bundle"):
        ResultBundle(
            bundle_kind=BundleKind.NORMAL,
            task_type=TaskType.DET,
            items=(item,),
        )


def test_normal_bundle_rejects_empty_seg_has_foreground_false() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(
            mask_ref="manual_masks/img-1_manual.png",
            has_foreground=False,
        ),
        human_confirmed=True,
        needs_rework=False,
    )
    with pytest.raises(ValueError, match="NORMAL bundle"):
        ResultBundle(
            bundle_kind=BundleKind.NORMAL,
            task_type=TaskType.SEG,
            items=(item,),
        )


def test_rework_bundle_accepts_unconfirmed_without_needs_rework_flag() -> None:
    """human_confirmed=False counts as should_rework even if needs_rework=False."""

    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=False,
        needs_rework=False,
    )
    bundle = ResultBundle(
        bundle_kind=BundleKind.REWORK,
        task_type=TaskType.DET,
        items=(item,),
    )
    assert bundle.items[0].image_id == "img-1"


def test_normal_bundle_rejects_unconfirmed_item() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.DET,
        annotation=DetAnnotation(bboxes=()),
        human_confirmed=False,
        needs_rework=False,
    )
    with pytest.raises(ValueError, match="NORMAL bundle"):
        ResultBundle(
            bundle_kind=BundleKind.NORMAL,
            task_type=TaskType.DET,
            items=(item,),
        )


def test_bundle_rejects_mismatched_item_task_type() -> None:
    item = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="m"),
        human_confirmed=True,
        needs_rework=False,
    )
    with pytest.raises(ValueError, match="item task_type"):
        ResultBundle(
            bundle_kind=BundleKind.NORMAL,
            task_type=TaskType.CAP,
            items=(item,),
        )


def test_frozen_image_record_is_immutable() -> None:
    image = ImageRecord(
        image_id="img-1",
        image_path="a.jpg",
        diagnosis_text="t",
    )
    with pytest.raises(AttributeError):
        image.image_id = "img-2"  # type: ignore[misc]


def test_current_version_semantics_by_replacement() -> None:
    """Overwrite semantics: replace object for same image_id + task_type."""

    first = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="v1"),
        human_confirmed=True,
        needs_rework=True,
        export_round=1,
    )
    second = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption="v2"),
        human_confirmed=True,
        needs_rework=False,
        export_round=2,
    )
    current = { (first.image_id, first.task_type): first }
    current[(second.image_id, second.task_type)] = second
    assert current[("img-1", TaskType.CAP)].annotation.caption == "v2"
    assert current[("img-1", TaskType.CAP)].needs_rework is False


def test_optional_fields_default_none() -> None:
    result = TaskAnnotationResult(
        image_id="img-1",
        task_type=TaskType.SEG,
        annotation=SegAnnotation(mask_ref="m"),
        human_confirmed=False,
        needs_rework=False,
    )
    image = ImageRecord(
        image_id="img-1",
        image_path="a.jpg",
        diagnosis_text="t",
    )
    assert result.package_id is None
    assert result.export_round is None
    assert image.batch_id is None
    assert image.source_image_name is None


def test_batch_context() -> None:
    ctx = BatchContext(batch_id="batch-a")
    assert ctx.batch_id == "batch-a"
