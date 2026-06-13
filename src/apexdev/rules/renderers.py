from __future__ import annotations
import xml.etree.ElementTree as ET
from jinja2 import Template
from .components import Component

def render_text(root: Component, template: str | None = None) -> str:
    if template:
        return Template(template).render(root=root, components=root.walk())
    lines = []
    for c in root.walk():
        indent = "  " * max(0, len(c.id.split(".")) - 1)
        lines.append(f"{indent}[{c.kind}] {c.text}")
    return "\n".join(lines)

def render_xml(root: Component) -> str:
    def build(c: Component) -> ET.Element:
        elem = ET.Element(c.kind, {"id": c.id, **{k: str(v) for k, v in c.attributes.items()}})
        elem.text = c.text
        for child in c.children:
            elem.append(build(child))
        return elem
    return ET.tostring(build(root), encoding="unicode")
