"""Load processed batch manifests (M1 read side)."""

from __future__ import annotations

from pathlib import Path

from mma.common.io import read_json
from mma.common.models import ImageRecord
from mma.common.paths import validate_batch_id


def load_processed_items(processed_dir: Path | str) -> tuple[ImageRecord, ...]:
    """Load ``ImageRecord`` rows from ``processed_dir/manifest.json``."""

    directory = Path(processed_dir)
    manifest_path = directory / "manifest.json"
    payload = read_json(manifest_path)

    if not isinstance(payload, dict):
        raise ValueError(f"processed manifest must be an object: {manifest_path}")

    batch_id = payload.get("batch_id")
    if not batch_id or not str(batch_id).strip():
        raise ValueError(f"processed manifest missing batch_id: {manifest_path}")
    batch_id = validate_batch_id(str(batch_id))

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"processed manifest has no items: {manifest_path}")

    records: list[ImageRecord] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"processed manifest item {index} must be an object")
        try:
            image_id = str(item["image_id"]).strip()
            image_path = str(item["image_path"]).strip()
            diagnosis_text = str(item["diagnosis_text"]).strip()
        except KeyError as exc:
            raise ValueError(
                f"processed manifest item {index} missing field {exc.args[0]!r}"
            ) from exc

        if not image_id or not image_path or not diagnosis_text:
            raise ValueError(
                f"processed manifest item {index} has empty required fields"
            )

        source_image_name = item.get("source_image_name")
        if source_image_name is None or str(source_image_name).strip() == "":
            source_image_name = Path(image_path).name
        else:
            source_image_name = str(source_image_name)

        records.append(
            ImageRecord(
                image_id=image_id,
                image_path=image_path,
                diagnosis_text=diagnosis_text,
                batch_id=batch_id,
                source_image_name=source_image_name,
            )
        )

    return tuple(records)
