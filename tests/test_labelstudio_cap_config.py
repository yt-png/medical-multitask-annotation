"""Static tests for CAP Label Studio labeling config (T3.3)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from mma.labelstudio import (
    CAP_CONFIG_NAME,
    cap_config_path,
    load_cap_config_text,
)


def _parse_config() -> ET.Element:
    return ET.fromstring(load_cap_config_text())


def _find_all(root: ET.Element, tag: str) -> list[ET.Element]:
    return list(root.iter(tag))


def test_cap_config_packaged_and_readable() -> None:
    path = cap_config_path()
    assert path.name == CAP_CONFIG_NAME
    assert path.is_file()
    text = load_cap_config_text()
    assert text.strip()
    assert "<TextArea" in text


def test_cap_config_well_formed_xml() -> None:
    root = _parse_config()
    assert root.tag == "View"


def test_cap_image_and_textarea_binding() -> None:
    root = _parse_config()
    images = _find_all(root, "Image")
    assert len(images) == 1
    image = images[0]
    assert image.get("name") == "image"
    assert image.get("value") == "$image"

    areas = _find_all(root, "TextArea")
    assert len(areas) == 1
    area = areas[0]
    assert area.get("name") == "cap_text"
    assert area.get("toName") == "image"


def test_cap_diagnosis_readonly_not_editable_control() -> None:
    root = _parse_config()
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$diagnosis_text" in text_values

    areas = _find_all(root, "TextArea")
    assert len(areas) == 1
    assert areas[0].get("name") == "cap_text"
    assert areas[0].get("value") is None or areas[0].get("value") != "$diagnosis_text"


def test_cap_no_brush_rectangle_or_mask_ref() -> None:
    root = _parse_config()
    assert _find_all(root, "BrushLabels") == []
    assert _find_all(root, "RectangleLabels") == []
    for image in _find_all(root, "Image"):
        assert image.get("value") != "$mask_ref"
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$mask_ref" not in text_values


def test_cap_readonly_ids() -> None:
    root = _parse_config()
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$image_id" in text_values
    assert "$package_id" in text_values


def test_cap_human_confirmed_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "human_confirmed"
    ]
    assert len(choices) == 1
    human = choices[0]
    assert human.get("required") == "true"
    values = {el.get("value") for el in human.findall("Choice")}
    assert values == {"yes", "no"}


def test_cap_config_has_no_prediction_or_prelabel() -> None:
    text = load_cap_config_text()
    assert "预标注" not in text
    lowered = text.lower()
    assert "prediction" not in lowered
    assert "prelabel" not in lowered
    headers = [
        el.get("value") for el in _find_all(_parse_config(), "Header")
    ]
    assert "人工描述" in headers


def test_cap_needs_rework_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "needs_rework"
    ]
    assert len(choices) == 1
    rework = choices[0]
    assert rework.get("required") in (None, "false")
    values = {el.get("value") for el in rework.findall("Choice")}
    assert values == {"yes", "no"}
