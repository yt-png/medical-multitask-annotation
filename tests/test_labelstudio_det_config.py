"""Static tests for DET Label Studio labeling config (T3.2)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from mma.labelstudio import (
    DET_CONFIG_NAME,
    det_config_path,
    load_det_config_text,
)


def _parse_config() -> ET.Element:
    return ET.fromstring(load_det_config_text())


def _find_all(root: ET.Element, tag: str) -> list[ET.Element]:
    return list(root.iter(tag))


def test_det_config_packaged_and_readable() -> None:
    path = det_config_path()
    assert path.name == DET_CONFIG_NAME
    assert path.is_file()
    text = load_det_config_text()
    assert text.strip()
    assert "<RectangleLabels" in text


def test_det_config_well_formed_xml() -> None:
    root = _parse_config()
    assert root.tag == "View"


def test_det_image_and_rectangle_binding() -> None:
    root = _parse_config()
    images = _find_all(root, "Image")
    assert len(images) == 1
    image = images[0]
    assert image.get("name") == "image"
    assert image.get("value") == "$image"

    rects = _find_all(root, "RectangleLabels")
    assert len(rects) == 1
    rect = rects[0]
    assert rect.get("name") == "det_bbox"
    assert rect.get("toName") == "image"

    labels = [el.get("value") for el in rect.findall("Label")]
    assert labels == ["object"]


def test_det_no_brush_or_mask_ref_main_image() -> None:
    root = _parse_config()
    assert _find_all(root, "BrushLabels") == []
    for image in _find_all(root, "Image"):
        assert image.get("value") != "$mask_ref"
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$mask_ref" not in text_values


def test_det_readonly_diagnosis_and_ids() -> None:
    root = _parse_config()
    text_values = {el.get("value") for el in _find_all(root, "Text")}
    assert "$diagnosis_text" in text_values
    assert "$image_id" in text_values
    assert "$package_id" in text_values

    for image in _find_all(root, "Image"):
        assert image.get("value") == "$image"


def test_det_human_confirmed_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "human_confirmed"
    ]
    assert len(choices) == 1
    human = choices[0]
    assert human.get("required") == "true"
    values = {el.get("value") for el in human.findall("Choice")}
    assert values == {"yes", "no"}


def test_det_needs_rework_choices() -> None:
    root = _parse_config()
    choices = [
        el for el in _find_all(root, "Choices") if el.get("name") == "needs_rework"
    ]
    assert len(choices) == 1
    rework = choices[0]
    assert rework.get("required") in (None, "false")
    values = {el.get("value") for el in rework.findall("Choice")}
    assert values == {"yes", "no"}
