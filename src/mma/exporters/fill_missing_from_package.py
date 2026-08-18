"""Fill task-package samples missing from an LS export into empty results.

R1: samples in ``task_packages/<batch>/<task>/manifest.json`` that are in
neither the current export nor existing ``current/`` become empty
``TaskAnnotationResult`` records (unconfirmed, no effective payload) so
``should_rework_result`` sends them to ``rework/``.

Does not change ``overwrite_current`` merge semantics: ids already in
``current/`` and absent from this export are left untouched.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from mma.common.io import read_json
from mma.common.models import (
    CapAnnotation,
    DetAnnotation,
    SegAnnotation,
    TaskAnnotationResult,
    TaskType,
)
from mma.common.paths import (
    results_current_dir,
    results_manual_masks_dir,
    task_dir_name,
    task_package_dir,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.converters.seg_brush import write_empty_manual_mask
from mma.exporters.current_annotations import ANNOTATIONS_JSON_NAME
from mma.exporters.load_current import load_current

_MAX_IDS_IN_MESSAGE = 20


def fill_missing_from_package(
    parsed: Sequence[TaskAnnotationResult],
    *,
    batch_id: str,
    task_type: TaskType,
    data_root: Path,
    export_round: int | None = None,
) -> tuple[TaskAnnotationResult, ...]:
    """Return ``parsed`` plus empty placeholders for unseen package samples.

    Requires a task-package manifest. Export ``image_id`` values that are not
    in the package raise ``ValueError``. Placeholders:

    ``package_ids - export_ids - already_in_current_ids``

    in manifest order. SEG placeholders write an empty ``manual_masks/`` file.
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")

    package_id, package_ids = _load_package_image_ids(
        batch_id, task_type=task_type, data_root=data_root
    )
    package_set = set(package_ids)

    export_set: set[str] = set()
    for index, item in enumerate(parsed):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"parsed[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if item.task_type is not task_type:
            raise ValueError(
                f"parsed[{index}] task_type {item.task_type.value} does not "
                f"match requested {task_type.value}"
            )
        if item.image_id in export_set:
            raise ValueError(
                f"duplicate image_id in export parse: {item.image_id!r}"
            )
        export_set.add(item.image_id)

    extra = sorted(export_set - package_set)
    if extra:
        raise ValueError(
            "export contains image_id values not in task package "
            f"(batch_id={batch_id!r}, task={task_dir_name(task_type)!r}): "
            + _format_id_list(extra)
        )

    current_ids = _existing_current_ids(
        batch_id, task_type=task_type, data_root=data_root
    )
    placeholders = [
        image_id
        for image_id in package_ids
        if image_id not in export_set and image_id not in current_ids
    ]

    filled: list[TaskAnnotationResult] = list(parsed)
    for image_id in placeholders:
        filled.append(
            _empty_placeholder(
                image_id,
                batch_id=batch_id,
                task_type=task_type,
                package_id=package_id,
                data_root=data_root,
                export_round=export_round,
            )
        )
    return tuple(filled)


def _load_package_image_ids(
    batch_id: str,
    *,
    task_type: TaskType,
    data_root: Path,
) -> tuple[str, list[str]]:
    """Return ``(package_id, ordered image_id list)`` from the task package."""

    package_dir = task_package_dir(batch_id, task_type, data_root=data_root)
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"task package manifest not found: {manifest_path} "
            f"(batch_id={batch_id!r}, task={task_dir_name(task_type)!r})"
        )
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"task package manifest must be an object: {manifest_path}"
        )

    raw_package_id = payload.get("package_id")
    if not isinstance(raw_package_id, str) or not raw_package_id.strip():
        raise ValueError(
            f"task package manifest missing non-empty package_id: "
            f"{manifest_path}"
        )
    package_id = raw_package_id.strip()

    samples_raw = payload.get("samples")
    if not isinstance(samples_raw, list) or not samples_raw:
        raise ValueError(
            f"task package manifest has no samples: {manifest_path}"
        )

    image_ids: list[str] = []
    seen: set[str] = set()
    for index, sample in enumerate(samples_raw):
        if not isinstance(sample, dict):
            raise ValueError(
                f"task package manifest sample at index {index} must be an object"
            )
        raw_id = sample.get("image_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError(
                f"task package manifest sample at index {index} "
                "missing non-empty image_id"
            )
        image_id = raw_id.strip()
        if image_id in seen:
            raise ValueError(
                f"duplicate image_id in task package manifest: {image_id!r}"
            )
        seen.add(image_id)
        image_ids.append(image_id)
    return package_id, image_ids


def _existing_current_ids(
    batch_id: str,
    *,
    task_type: TaskType,
    data_root: Path,
) -> set[str]:
    path = results_current_dir(batch_id, task_type, data_root=data_root) / (
        ANNOTATIONS_JSON_NAME
    )
    if not path.is_file():
        return set()
    return {
        item.image_id
        for item in load_current(batch_id, task_type, data_root=data_root)
    }


def _empty_placeholder(
    image_id: str,
    *,
    batch_id: str,
    task_type: TaskType,
    package_id: str,
    data_root: Path,
    export_round: int | None,
) -> TaskAnnotationResult:
    if task_type is TaskType.CAP:
        annotation: CapAnnotation | DetAnnotation | SegAnnotation = CapAnnotation(
            caption=""
        )
    elif task_type is TaskType.DET:
        annotation = DetAnnotation(bboxes=())
    elif task_type is TaskType.SEG:
        annotation = _empty_seg_annotation(
            image_id, batch_id=batch_id, data_root=data_root
        )
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError(f"unsupported task type: {task_type!r}")

    return TaskAnnotationResult(
        image_id=image_id,
        task_type=task_type,
        annotation=annotation,
        human_confirmed=False,
        needs_rework=False,
        package_id=package_id,
        export_round=export_round,
    )


def _empty_seg_annotation(
    image_id: str,
    *,
    batch_id: str,
    data_root: Path,
) -> SegAnnotation:
    image_path = resolve_task_image_path(
        batch_id,
        TaskType.SEG,
        image_id,
        data_root=data_root,
    )
    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except OSError as exc:
        raise ValueError(
            f"failed to read image for empty SEG placeholder: {image_path} "
            f"(image_id={image_id!r})"
        ) from exc

    mask_ref = write_empty_manual_mask(
        image_id=image_id,
        width=width,
        height=height,
        manual_mask_dir=results_manual_masks_dir(batch_id, data_root=data_root),
    )
    return SegAnnotation(mask_ref=mask_ref, has_foreground=False)


def _format_id_list(ids: Sequence[str]) -> str:
    total = len(ids)
    shown = list(ids[:_MAX_IDS_IN_MESSAGE])
    text = ", ".join(shown)
    if total > _MAX_IDS_IN_MESSAGE:
        text += f" ... ({total} total)"
    else:
        text += f" ({total} total)"
    return text
