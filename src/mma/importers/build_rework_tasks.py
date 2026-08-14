"""Build Label Studio rework import tasks (T4.3).

Supports two prediction sources:

- ``previous``: self-contained ``rework/previous_annotations/`` (preferred)
- ``raw``: legacy side-channel from an LS export JSON
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from mma.common.io import read_json
from mma.common.models import SegAnnotation, TaskAnnotationResult, TaskType
from mma.common.paths import (
    default_data_root,
    task_dir_name,
    task_package_dir,
    validate_batch_id,
)
from mma.common.task_image_paths import resolve_task_image_path
from mma.converters.to_labelstudio import (
    DATA_KEY_BATCH_ID,
    DATA_KEY_DIAGNOSIS_TEXT,
    DATA_KEY_IMAGE,
    DATA_KEY_IMAGE_ID,
    DATA_KEY_MASK_REF,
    DATA_KEY_PACKAGE_ID,
)
from mma.exporters.previous_annotations import (
    PREVIOUS_ANNOTATIONS_DIRNAME,
    build_ls_prediction_results_from_previous,
    load_previous_annotations,
    previous_annotations_dir,
)
from mma.importers.build_ls_tasks import rewrite_task_image_urls

REWORK_MODEL_VERSION = "mma-rework-prev-1.0"
_CHOICE_FROM_NAMES = frozenset({"human_confirmed", "needs_rework"})
PredictionSource = Literal["previous", "raw"]


def build_rework_ls_tasks(
    rework_results: Sequence[TaskAnnotationResult],
    *,
    batch_id: str,
    task_type: TaskType,
    prediction_source: PredictionSource = "raw",
    raw_results_by_image_id: Mapping[str, Sequence[Mapping[str, Any]]]
    | None = None,
    data_root: Path | str | None = None,
    local_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Build LS import tasks for rework samples.

    ``prediction_source``:

    - ``\"previous\"``: load ``rework/previous_annotations/<task>.json`` and
      build ``predictions`` (DET/SEG/CAP converters reused).
    - ``\"raw\"``: use ``raw_results_by_image_id`` after stripping Choices
      (legacy export side-channel).
    """

    if not isinstance(task_type, TaskType):
        raise ValueError(f"task_type must be TaskType, got {type(task_type)!r}")
    if prediction_source not in ("previous", "raw"):
        raise ValueError(
            f"prediction_source must be 'previous' or 'raw', "
            f"got {prediction_source!r}"
        )

    cleaned = validate_batch_id(batch_id)
    root = default_data_root() if data_root is None else Path(data_root)
    local = root if local_root is None else Path(local_root)
    task_key = task_dir_name(task_type)

    if not rework_results:
        return []

    manifest = _load_task_package_manifest(
        cleaned, task_type=task_type, data_root=root
    )
    samples_by_id = _index_manifest_samples(manifest, task_type=task_type)

    previous_by_id: dict[str, dict[str, Any]] | None = None
    previous_root: Path | None = None
    if prediction_source == "previous":
        previous_by_id = load_previous_annotations(
            cleaned, task_type, data_root=root
        )
        previous_root = previous_annotations_dir(
            cleaned, task_type, data_root=root
        )
    else:
        if raw_results_by_image_id is None:
            raise ValueError(
                "raw_results_by_image_id is required when "
                "prediction_source='raw'"
            )

    tasks: list[dict[str, Any]] = []
    image_paths_by_id: dict[str, Path] = {}

    for index, item in enumerate(rework_results):
        if not isinstance(item, TaskAnnotationResult):
            raise TypeError(
                f"rework_results[{index}] must be TaskAnnotationResult, "
                f"got {type(item).__name__}"
            )
        if item.task_type is not task_type:
            raise ValueError(
                f"rework item task_type {item.task_type.value} does not match "
                f"requested {task_type.value} (image_id={item.image_id!r})"
            )

        image_id = item.image_id
        if image_id not in samples_by_id:
            raise ValueError(
                f"image_id={image_id!r} not found in task package manifest "
                f"(batch_id={cleaned!r}, task={task_key!r})"
            )

        sample = samples_by_id[image_id]
        image_path = resolve_task_image_path(
            cleaned, task_key, image_id, data_root=root
        )
        image_paths_by_id[image_id] = image_path

        if prediction_source == "previous":
            assert previous_by_id is not None and previous_root is not None
            if image_id not in previous_by_id:
                raise ValueError(
                    f"missing previous_annotations entry for "
                    f"image_id={image_id!r} under {PREVIOUS_ANNOTATIONS_DIRNAME}/"
                )
            width: int | None = None
            height: int | None = None
            if task_type is TaskType.DET:
                width, height = _image_size(image_path, image_id=image_id)
            prediction_result = build_ls_prediction_results_from_previous(
                previous_by_id[image_id],
                task_type=task_type,
                image_id=image_id,
                previous_root=previous_root,
                image_width=width,
                image_height=height,
                package_id=sample["package_id"],
                batch_id=cleaned,
            )
        else:
            assert raw_results_by_image_id is not None
            if image_id not in raw_results_by_image_id:
                raise ValueError(
                    f"missing raw LS result side channel for "
                    f"image_id={image_id!r}"
                )
            prediction_result = _strip_choice_controls(
                raw_results_by_image_id[image_id],
                image_id=image_id,
            )

        data: dict[str, Any] = {
            DATA_KEY_IMAGE: None,
            DATA_KEY_DIAGNOSIS_TEXT: sample["diagnosis_text"],
            DATA_KEY_IMAGE_ID: image_id,
            DATA_KEY_PACKAGE_ID: sample["package_id"],
            DATA_KEY_BATCH_ID: cleaned,
        }
        if task_type is TaskType.SEG:
            if prediction_source == "previous":
                assert previous_by_id is not None
                mask_file = previous_by_id[image_id].get("mask_file")
                if isinstance(mask_file, str) and mask_file.strip():
                    data[DATA_KEY_MASK_REF] = (
                        f"{PREVIOUS_ANNOTATIONS_DIRNAME}/"
                        f"{mask_file.strip().replace(chr(92), '/')}"
                    )
                elif isinstance(item.annotation, SegAnnotation):
                    data[DATA_KEY_MASK_REF] = item.annotation.mask_ref
            elif isinstance(item.annotation, SegAnnotation):
                data[DATA_KEY_MASK_REF] = item.annotation.mask_ref

        tasks.append(
            {
                "id": image_id,
                "data": data,
                "predictions": [
                    {
                        "model_version": REWORK_MODEL_VERSION,
                        "result": prediction_result,
                    }
                ],
            }
        )

    return rewrite_task_image_urls(
        tasks,
        image_paths_by_id=image_paths_by_id,
        local_root=local,
    )


def _image_size(image_path: Path, *, image_id: str) -> tuple[int, int]:
    try:
        with Image.open(image_path) as img:
            return img.size
    except OSError as exc:
        raise ValueError(
            f"failed to read image size for image_id={image_id!r}: {image_path}"
        ) from exc


def _load_task_package_manifest(
    batch_id: str,
    *,
    task_type: TaskType,
    data_root: Path,
) -> dict[str, Any]:
    package_dir = task_package_dir(batch_id, task_type, data_root=data_root)
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"task package manifest not found: {manifest_path} "
            f"(batch_id={batch_id!r}, task={task_dir_name(task_type)!r})"
        )
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError(f"task package manifest must be an object: {manifest_path}")
    return payload


def _index_manifest_samples(
    manifest: dict[str, Any],
    *,
    task_type: TaskType,
) -> dict[str, dict[str, str]]:
    package_id = manifest.get("package_id")
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError("task package manifest missing non-empty package_id")

    manifest_task = manifest.get("task_type")
    if isinstance(manifest_task, str) and manifest_task.strip():
        if manifest_task.strip().upper() != task_type.value:
            raise ValueError(
                f"manifest task_type {manifest_task!r} does not match "
                f"requested {task_type.value}"
            )

    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("task package manifest has no samples")

    by_id: dict[str, dict[str, str]] = {}
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"manifest sample at index {index} must be an object")
        try:
            image_id = str(sample["image_id"]).strip()
            diagnosis_text = str(sample["diagnosis_text"]).strip()
        except KeyError as exc:
            raise ValueError(
                f"manifest sample at index {index} missing field {exc.args[0]!r}"
            ) from exc
        if not image_id or not diagnosis_text:
            raise ValueError(
                f"manifest sample at index {index} has empty required fields"
            )
        if image_id in by_id:
            raise ValueError(
                f"duplicate image_id in task package manifest: {image_id!r}"
            )
        by_id[image_id] = {
            "diagnosis_text": diagnosis_text,
            "package_id": package_id.strip(),
        }
    return by_id


def _strip_choice_controls(
    raw_result: Sequence[Mapping[str, Any]],
    *,
    image_id: str,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for entry in raw_result:
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"raw LS result entry must be an object (image_id={image_id!r})"
            )
        from_name = entry.get("from_name")
        if from_name in _CHOICE_FROM_NAMES:
            continue
        filtered.append(copy.deepcopy(dict(entry)))
    return filtered
