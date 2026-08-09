"""Assign package_id and write task-package manifests (T1.5)."""

from __future__ import annotations

from pathlib import Path

from mma.common.ids import generate_package_id
from mma.common.io import write_json
from mma.common.models import TaskPackage, TaskType
from mma.common.paths import (
    task_package_dir,
    task_packages_batch_dir,
    validate_batch_id,
)
from mma.packaging.split_task_packages import split_task_packages

_TASK_TYPES = (TaskType.SEG, TaskType.DET, TaskType.CAP)


def _assert_sample_images_exist(package: TaskPackage, package_dir: Path) -> None:
    for sample in package.samples:
        image_path = package_dir / sample.image_path
        if not image_path.is_file():
            raise ValueError(
                f"package image missing for image_id={sample.image_id!r}: "
                f"{image_path}"
            )


def _package_to_manifest_dict(package: TaskPackage) -> dict[str, object]:
    if package.batch_id is None:
        raise ValueError("TaskPackage.batch_id must not be None when writing manifest")
    return {
        "package_id": package.package_id,
        "task_type": package.task_type.value,
        "batch_id": package.batch_id,
        "samples": [
            {
                "image_id": sample.image_id,
                "image_path": sample.image_path,
                "diagnosis_text": sample.diagnosis_text,
            }
            for sample in package.samples
        ],
    }


def write_task_package_manifest(
    package: TaskPackage,
    package_dir: Path | str,
) -> Path:
    """Write ``manifest.json`` under ``package_dir`` (overwrite if exists)."""

    if not package.samples:
        raise ValueError("package samples must not be empty")

    directory = Path(package_dir)
    directory.mkdir(parents=True, exist_ok=True)
    _assert_sample_images_exist(package, directory)

    manifest_path = directory / "manifest.json"
    write_json(manifest_path, _package_to_manifest_dict(package))
    return manifest_path


def build_task_packages(
    batch_id: str,
    *,
    data_root: Path | str | None = None,
) -> dict[TaskType, TaskPackage]:
    """Split images (T1.4) then assign package_id and write manifests.

    Returns one ``TaskPackage`` per task type.
    """

    cleaned = validate_batch_id(batch_id)
    samples_by_task = split_task_packages(cleaned, data_root=data_root)

    packages: dict[TaskType, TaskPackage] = {}
    for task_type in _TASK_TYPES:
        samples = samples_by_task[task_type]
        if not samples:
            raise ValueError(f"no samples for task {task_type.value}")

        package = TaskPackage(
            package_id=generate_package_id(cleaned, task_type),
            task_type=task_type,
            samples=samples,
            batch_id=cleaned,
        )
        package_dir = task_package_dir(cleaned, task_type, data_root=data_root)
        write_task_package_manifest(package, package_dir)
        packages[task_type] = package

    # Ensure batch root exists for CLI path printing even if only nested dirs were made.
    task_packages_batch_dir(cleaned, data_root=data_root).mkdir(parents=True, exist_ok=True)
    return packages
