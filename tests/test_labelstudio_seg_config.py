"""Static tests for SEG Label Studio labeling config (T3.1)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from mma.labelstudio import (
    SEG_CONFIG_NAME,
    load_seg_config_text,
    seg_config_path,
)

# First-round ls-import data contract (no mask_ref).
_FIRST_ROUND_DATA_KEYS = frozenset(
    {"image", "image_id", "package_id", "diagnosis_text"}
)


def _parse_config() -> ET.Element:
    return ET.fromstring(load_seg_config_text())


def _find_all(root: ET.Element, tag: str) -> list[ET.Element]:
    return list(root.iter(tag))


def _xml_data_bindings(root: ET.Element) -> set[str]:
    """Return data-field names referenced as ``value="$field"``."""

    names: set[str] = set()
    for element in root.iter():
        value = element.get("value")
        if isinstance(value, str) and value.startswith("$") and len(value) > 1:
            names.add(value[1:])
    return names


def test_seg_config_packaged_and_readable() -> None:
    path = seg_config_path()
    assert path.name == SEG_CONFIG_NAME
    assert path.is_file()
    text = load_seg_config_text()
    assert text.strip()
    assert "<PolygonLabels" in text


def test_seg_config_well_formed_xml() -> None:
    root = _parse_config()
    assert root.tag == "View"


def test_seg_image_and_polygon_binding() -> None:
    root = _parse_config()
    images = _find_all(root, "Image")
    assert len(images) == 1
    image = images[0]
    assert image.get("name") == "image"
    assert image.get("value") == "$image"

    polygons = _find_all(root, "PolygonLabels")
    assert len(polygons) == 1
    polygon = polygons[0]
    assert polygon.get("name") == "seg_mask"
    assert polygon.get("toName") == "image"

    labels = [el.get("value") for el in polygon.findall("Label")]
    assert labels == ["lesion"]


def test_seg_no_mask_ref_as_main_image() -> None:
    root = _parse_config()
    for image in _find_all(root, "Image"):
        assert image.get("value") != "$mask_ref"


def test_seg_readonly_diagnosis_and_ids() -> None:
    root = _parse_config()
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$diagnosis_text" in text_values
    assert "$image_id" in text_values
    assert "$package_id" in text_values
    assert "$mask_ref" not in text_values

    for image in _find_all(root, "Image"):
        assert image.get("value") in {"$image"}


def test_seg_config_does_not_bind_mask_ref() -> None:
    """V1 first-round SEG config must not depend on ``$mask_ref``."""

    text = load_seg_config_text()
    assert "$mask_ref" not in text
    assert "mask_ref_view" not in text
    root = _parse_config()
    assert "mask_ref" not in _xml_data_bindings(root)


def test_seg_config_accepts_first_round_empty_task_data() -> None:
    """Four-field first-round ``data`` is sufficient to bind SEG XML."""

    root = _parse_config()
    bindings = _xml_data_bindings(root)
    assert bindings <= _FIRST_ROUND_DATA_KEYS
    assert bindings == {
        "image",
        "image_id",
        "package_id",
        "diagnosis_text",
    }


def test_seg_human_confirmed_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "human_confirmed"
    ]
    assert len(choices) == 1
    human = choices[0]
    assert human.get("required") == "true"
    values = {el.get("value") for el in human.findall("Choice")}
    assert values == {"yes", "no"}


def test_seg_config_has_no_prediction_or_prelabel() -> None:
    text = load_seg_config_text().lower()
    assert "prediction" not in text
    assert "prelabel" not in text


def test_seg_needs_rework_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "needs_rework"
    ]
    assert len(choices) == 1
    rework = choices[0]
    assert rework.get("required") == "true"
    values = {el.get("value") for el in rework.findall("Choice")}
    assert values == {"yes", "no"}


def test_seg_choice_fields_both_required_for_submit() -> None:
    """Both human_confirmed and needs_rework must block LS submit when unset."""

    root = _parse_config()
    required_names = {
        el.get("name")
        for el in _find_all(root, "Choices")
        if el.get("required") == "true"
    }
    assert required_names == {"human_confirmed", "needs_rework"}
