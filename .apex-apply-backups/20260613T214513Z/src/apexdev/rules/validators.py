from __future__ import annotations
from .components import Component

def validate_ids(root: Component) -> list[str]:
    seen, problems = set(), []
    for c in root.walk():
        if not c.id:
            problems.append("component has empty id")
        if c.id in seen:
            problems.append(f"duplicate component id: {c.id}")
        seen.add(c.id)
    return problems

def validate_text_leaves(root: Component) -> list[str]:
    return [f"leaf component has no text: {c.id}" for c in root.walk() if not c.children and not c.text.strip()]
