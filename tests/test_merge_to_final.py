"""Tests for final multitask dataset write / merge_to_final (T5.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mma.common.io import write_json
from mma.common.models import (
    BBox,
    CapAnnotation,
    DetAnnotation,
    MergedMultitaskRecord,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.converters.seg_brush import (
    load_foreground_mask,
    save_binary_mask_png,
    write_empty_manual_mask,
)
from mma.exporters import overwrite_current
from mma.merge import (
    assert_final_seg_mask_contract,
    final_image_path,
    final_seg_mask_ref,
    materialize_final_seg_mask,
    merge_to_final,
    write_final_manifest,
)
from mma.merge.write_final import FINAL_MANIFEST_NAME
from PIL import Image


def _seg(
    image_id: str,
    *,
    mask_ref: str | None = None,
) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.SEG,
        annotation=SegAnnotation(
            mask_ref=mask_ref or f"manual_masks/{image_id}_manual.png"
        ),
        human_confirmed=True,
        needs_rework=False,
    )


def _det(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.DET,
        annotation=DetAnnotation(
            bboxes=(BBox(x=1.0, y=2.0, width=3.0, height=4.0),)
        ),
        human_confirmed=True,
        needs_rework=False,
    )


def _cap(image_id: str) -> TaskAnnotationResult:
    return TaskAnnotationResult(
        image_id=image_id,
        task_type=TaskType.CAP,
        annotation=CapAnnotation(caption=f"cap-{image_id}"),
        human_confirmed=True,
        needs_rework=False,
    )


def _write_prelabel_mask(
    data_root: Path,
    batch_id: str,
    image_id: str,
    *,
    binary: list[list[int]] | None = None,
) -> Path:
    masks_dir = data_root / "prelabels" / batch_id / "seg" / "masks"
    path = masks_dir / f"{image_id}.png"
    pixels = binary or [[0, 1], [1, 0]]
    save_binary_mask_png(path, pixels)
    return path


def _write_manual_mask(
    data_root: Path,
    batch_id: str,
    image_id: str,
    *,
    binary: list[list[int]] | None = None,
    empty: bool = False,
) -> Path:
    mask_dir = data_root / "results" / batch_id / "seg" / "manual_masks"
    if empty:
        write_empty_manual_mask(
            image_id=image_id,
            width=2,
            height=2,
            manual_mask_dir=mask_dir,
        )
        return mask_dir / f"{image_id}_manual.png"
    pixels = binary or [[1, 0], [0, 1]]
    path = mask_dir / f"{image_id}_manual.png"
    save_binary_mask_png(path, pixels)
    return path


def _write_ready_currents(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
    *,
    write_manual_masks: bool = True,
) -> None:
    overwrite_current(
        [_seg(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.SEG,
        data_root=data_root,
    )
    overwrite_current(
        [_det(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.DET,
        data_root=data_root,
    )
    overwrite_current(
        [_cap(i) for i in image_ids],
        batch_id=batch_id,
        task_type=TaskType.CAP,
        data_root=data_root,
    )
    if write_manual_masks:
        for image_id in image_ids:
            _write_manual_mask(data_root, batch_id, image_id)


def _write_processed(
    data_root: Path,
    batch_id: str,
    image_ids: tuple[str, ...] = ("img-b", "img-a"),
    *,
    suffix: str = ".jpg",
) -> None:
    """Write processed manifest and real image files under a local images dir."""

    images_dir = data_root / "raw" / batch_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for image_id in image_ids:
        image_file = images_dir / f"{image_id}{suffix}"
        Image.new("RGB", (4, 4), color=(10, 20, 30)).save(image_file)
        items.append(
            {
                "image_id": image_id,
                "image_path": str(image_file.resolve()),
                "diagnosis_text": f"diag-{image_id}",
                "source_image_name": image_file.name,
            }
        )
    write_json(
        data_root / "processed" / batch_id / "manifest.json",
        {"batch_id": batch_id, "items": items},
    )


def test_write_final_manifest_shape(tmp_path: Path) -> None:
    records = (
        MergedMultitaskRecord(
            image_id="img-a",
            seg=SegAnnotation(mask_ref="m.png"),
            det=DetAnnotation(bboxes=(BBox(x=0.0, y=0.0, width=1.0, height=1.0),)),
            cap=CapAnnotation(caption="c"),
            image_path="/a.jpg",
            diagnosis_text="d",
        ),
    )
    path = write_final_manifest(records, batch_id="batch1", data_root=tmp_path)
    assert path == tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch1"
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["image_id"] == "img-a"
    assert item["image_path"] == "/a.jpg"
    assert item["diagnosis_text"] == "d"
    assert item["seg"] == {"mask_ref": "m.png"}
    assert item["det"]["bboxes"][0]["width"] == 1.0
    assert item["cap"] == {"caption": "c"}


def test_merge_to_final_success_order_and_enrich(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1")
    _write_processed(tmp_path, "batch1")
    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "batch1"
    assert [item["image_id"] for item in payload["items"]] == ["img-b", "img-a"]
    first = payload["items"][0]
    assert first["image_path"] == final_image_path("img-b")
    assert first["diagnosis_text"] == "diag-img-b"
    assert first["seg"]["mask_ref"] == final_seg_mask_ref("img-b")
    assert first["cap"]["caption"] == "cap-img-b"
    assert (tmp_path / "final" / "batch1" / "images" / "img-b.jpg").is_file()
    assert (tmp_path / "final" / "batch1" / "masks" / "img-b.png").is_file()


def test_merge_to_final_jpeg_source_becomes_jpg_name(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",), suffix=".jpeg")
    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["items"][0]["image_path"] == "images/img-a.jpg"
    assert (tmp_path / "final" / "batch1" / "images" / "img-a.jpg").is_file()
    assert not (tmp_path / "final" / "batch1" / "images" / "img-a.jpeg").exists()


def test_merge_to_final_overwrites(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    path = merge_to_final("batch1", data_root=tmp_path)
    path.write_text('{"batch_id":"batch1","items":[]}\n', encoding="utf-8")
    merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 1
    assert payload["items"][0]["image_id"] == "img-a"
    assert payload["items"][0]["seg"]["mask_ref"] == final_seg_mask_ref("img-a")


def test_merge_to_final_not_ready_preserves_old(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    path = merge_to_final("batch1", data_root=tmp_path)
    old = path.read_text(encoding="utf-8")
    overwrite_current(
        [
            TaskAnnotationResult(
                image_id="img-a",
                task_type=TaskType.CAP,
                annotation=CapAnnotation(caption="x"),
                human_confirmed=True,
                needs_rework=True,
            )
        ],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    with pytest.raises(ValueError, match="needs_rework"):
        merge_to_final("batch1", data_root=tmp_path)
    assert path.read_text(encoding="utf-8") == old


def test_merge_to_final_missing_task_does_not_write(tmp_path: Path) -> None:
    overwrite_current(
        [_seg("img-a"), _seg("img-b")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det("img-a"), _det("img-b")],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap("img-a")],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    with patch("mma.merge.merge_multitask.validate_ready", return_value=None):
        with pytest.raises(ValueError, match="missing CAP"):
            merge_to_final("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_merge_to_final_missing_processed(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a",))
    with pytest.raises(FileNotFoundError, match="processed manifest"):
        merge_to_final("batch1", data_root=tmp_path)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_merge_to_final_missing_processed_image_id(tmp_path: Path) -> None:
    _write_ready_currents(tmp_path, "batch1", image_ids=("img-a", "img-b"))
    _write_processed(tmp_path, "batch1", image_ids=("img-a",))
    with pytest.raises(ValueError, match="does not match processed") as exc:
        merge_to_final("batch1", data_root=tmp_path)
    assert "only_in_current" in str(exc.value)
    assert "img-b" in str(exc.value)
    assert not (tmp_path / "final" / "batch1" / FINAL_MANIFEST_NAME).exists()


def test_invalid_batch_id_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_id"):
        merge_to_final("bad/id", data_root=tmp_path)


def test_case1_manual_mask_materializes_to_final_masks(tmp_path: Path) -> None:
    """Case1: manual_masks/{id}_manual.png → masks/{id}.png."""

    image_id = "a"
    binary = [[1, 0], [0, 1]]
    _write_manual_mask(tmp_path, "batch1", image_id, binary=binary)
    overwrite_current(
        [_seg(image_id, mask_ref=f"manual_masks/{image_id}_manual.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det(image_id)],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap(image_id)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=(image_id,))

    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["items"][0]["seg"]["mask_ref"] == final_seg_mask_ref(image_id)
    assert payload["items"][0]["image_path"] == final_image_path(image_id)
    out = tmp_path / "final" / "batch1" / "masks" / f"{image_id}.png"
    assert out.is_file()
    loaded, width, height = load_foreground_mask(out)
    assert (width, height) == (2, 2)
    assert loaded == binary


def test_case2_legacy_prelabel_mask_ref_rejected(tmp_path: Path) -> None:
    """Case2: legacy ``masks/...`` (prelabels) is not a V1 resolve fallback."""

    image_id = "a"
    binary = [[0, 1], [1, 1]]
    _write_prelabel_mask(tmp_path, "batch1", image_id, binary=binary)
    overwrite_current(
        [_seg(image_id, mask_ref=f"masks/{image_id}.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det(image_id)],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap(image_id)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=(image_id,))

    with pytest.raises(ValueError, match="manual_masks|not a V1 fallback"):
        merge_to_final("batch1", data_root=tmp_path)


def test_case3_empty_manual_mask_is_copied_not_regenerated(tmp_path: Path) -> None:
    """Case3: empty manual mask is copied as-is into final masks/."""

    image_id = "a"
    _write_manual_mask(tmp_path, "batch1", image_id, empty=True)
    overwrite_current(
        [_seg(image_id, mask_ref=f"manual_masks/{image_id}_manual.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    overwrite_current(
        [_det(image_id)],
        batch_id="batch1",
        task_type=TaskType.DET,
        data_root=tmp_path,
    )
    overwrite_current(
        [_cap(image_id)],
        batch_id="batch1",
        task_type=TaskType.CAP,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=(image_id,))

    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["items"][0]["seg"]["mask_ref"] == final_seg_mask_ref(image_id)
    out = tmp_path / "final" / "batch1" / "masks" / f"{image_id}.png"
    loaded, width, height = load_foreground_mask(out)
    assert (width, height) == (2, 2)
    assert loaded == [[0, 0], [0, 0]]


def test_case4_all_final_mask_refs_use_unified_prefix(tmp_path: Path) -> None:
    """Case4: after merge every seg.mask_ref is masks/{image_id}.png."""

    ids = ("img-b", "img-a")
    _write_ready_currents(tmp_path, "batch1", image_ids=ids)
    # Mix one manual override
    _write_manual_mask(tmp_path, "batch1", "img-a", binary=[[1, 1], [0, 0]])
    overwrite_current(
        [_seg("img-a", mask_ref="manual_masks/img-a_manual.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=ids)

    path = merge_to_final("batch1", data_root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    refs = [item["seg"]["mask_ref"] for item in payload["items"]]
    assert refs
    for item in payload["items"]:
        ref = item["seg"]["mask_ref"]
        assert ref.startswith("masks/")
        assert ref == final_seg_mask_ref(item["image_id"])
        assert item["image_path"] == final_image_path(item["image_id"])
        assert "final_assets/" not in ref
        assert "manual_masks/" not in ref
        assert "prelabels/" not in ref


def test_assert_final_seg_mask_contract_rejects_legacy_roots() -> None:
    good = MergedMultitaskRecord(
        image_id="a",
        seg=SegAnnotation(mask_ref=final_seg_mask_ref("a")),
        det=DetAnnotation(bboxes=()),
        cap=CapAnnotation(caption="c"),
    )
    assert_final_seg_mask_contract((good,))

    bad = MergedMultitaskRecord(
        image_id="a",
        seg=SegAnnotation(mask_ref="final_assets/masks/a.png"),
        det=DetAnnotation(bboxes=()),
        cap=CapAnnotation(caption="c"),
    )
    with pytest.raises(ValueError, match="mask_ref contract"):
        assert_final_seg_mask_contract((bad,))


def test_materialize_final_seg_mask_copies_file(tmp_path: Path) -> None:
    image_id = "x"
    _write_manual_mask(tmp_path, "batch1", image_id, binary=[[1, 0], [0, 0]])
    out = materialize_final_seg_mask(
        image_id=image_id,
        seg=SegAnnotation(mask_ref=f"manual_masks/{image_id}_manual.png"),
        batch_id="batch1",
        data_root=tmp_path,
    )
    assert out.mask_ref == final_seg_mask_ref(image_id)
    assert out.has_foreground is True
    assert (tmp_path / "final" / "batch1" / "masks" / "x.png").is_file()


def test_final_self_contained_after_deleting_sources(tmp_path: Path) -> None:
    """After merge, deleting raw/processed/prelabels/manual_masks still works."""

    import shutil

    ids = ("img-b", "img-a")
    _write_ready_currents(tmp_path, "batch1", image_ids=ids)
    _write_manual_mask(tmp_path, "batch1", "img-a", binary=[[1, 0], [0, 1]])
    overwrite_current(
        [_seg("img-a", mask_ref="manual_masks/img-a_manual.png")],
        batch_id="batch1",
        task_type=TaskType.SEG,
        data_root=tmp_path,
    )
    _write_processed(tmp_path, "batch1", image_ids=ids)

    path = merge_to_final("batch1", data_root=tmp_path)
    final_dir = path.parent

    for name in ("raw", "processed", "prelabels"):
        target = tmp_path / name
        if target.exists():
            shutil.rmtree(target)
    manual = tmp_path / "results" / "batch1" / "seg" / "manual_masks"
    if manual.exists():
        shutil.rmtree(manual)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 2
    for item in payload["items"]:
        image_rel = item["image_path"]
        mask_rel = item["seg"]["mask_ref"]
        assert not Path(image_rel).is_absolute()
        assert not Path(mask_rel).is_absolute()
        assert (final_dir / image_rel).is_file()
        assert (final_dir / mask_rel).is_file()
        assert image_rel == final_image_path(item["image_id"])
        assert mask_rel == final_seg_mask_ref(item["image_id"])
