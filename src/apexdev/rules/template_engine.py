from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable


@dataclass(slots=True)
class Atom:
    text: str
    cost: int = 1
    tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class Literal:
    text: str


@dataclass(slots=True)
class Slot:
    name: str
    candidates: list[Atom]
    optional: bool = False


@dataclass
class Template:
    parts: list[Literal | Slot]
    alternatives: list["Template"] = field(default_factory=list)

    def slot(self, name: str) -> Slot:
        for part in self.parts:
            if isinstance(part, Slot) and part.name == name:
                return part
        raise KeyError(name)

    def append(self, part: Literal | Slot) -> None:
        self.parts.append(part)

    def insert_before(self, target_name: str, part: Literal | Slot) -> None:
        for i, existing in enumerate(self.parts):
            if isinstance(existing, Slot) and existing.name == target_name:
                self.parts.insert(i, part)
                return
        self.parts.append(part)


@dataclass(slots=True)
class RenderContext:
    desired_tags: set[str] = field(default_factory=set)
    forbidden_tags: set[str] = field(default_factory=set)
    max_cost: int = 12
    beam_width: int = 12


@dataclass(slots=True)
class PathState:
    text: str = ""
    cost: int = 0
    tags: set[str] = field(default_factory=set)

    def emit(self, text: str, cost: int = 0, tags: set[str] | None = None) -> "PathState":
        tags = tags or set()
        sep = "" if not self.text or text.startswith((".", ",", "!", "?")) else " "
        return PathState(self.text + sep + text, self.cost + cost, self.tags | tags)


def _score(path: PathState, ctx: RenderContext) -> float:
    desired_hits = len(path.tags & ctx.desired_tags)
    forbidden_hits = len(path.tags & ctx.forbidden_tags)
    over_cost = max(0, path.cost - ctx.max_cost)
    return desired_hits * 3 - forbidden_hits * 8 - over_cost * 2 - path.cost * 0.05


def prune_beam(paths: list[PathState], ctx: RenderContext) -> list[PathState]:
    return sorted(paths, key=lambda p: _score(p, ctx), reverse=True)[:ctx.beam_width]


def traverse(template: Template, ctx: RenderContext) -> PathState:
    paths = [PathState()]
    for part in template.parts:
        new_paths: list[PathState] = []
        for path in paths:
            if isinstance(part, Literal):
                new_paths.append(path.emit(part.text, cost=len(part.text.split())))
            elif isinstance(part, Slot):
                if part.optional:
                    new_paths.append(path)
                for atom in part.candidates:
                    if atom.tags & ctx.forbidden_tags:
                        continue
                    new_paths.append(path.emit(atom.text, atom.cost, set(atom.tags)))
        paths = prune_beam(new_paths, ctx)
    for alt in template.alternatives:
        paths.append(traverse(alt, ctx))
    return prune_beam(paths, ctx)[0]
