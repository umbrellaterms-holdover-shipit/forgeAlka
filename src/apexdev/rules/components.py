from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass(slots=True)
class Component:
    kind: str
    id: str
    text: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list["Component"] = field(default_factory=list)

    def add(self, child: "Component") -> "Component":
        self.children.append(child)
        return self

    def walk(self) -> list["Component"]:
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["children"] = [c.to_dict() for c in self.children]
        return d
