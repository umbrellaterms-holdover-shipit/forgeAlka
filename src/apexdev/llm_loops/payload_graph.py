from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class PayloadGraph:
    edges: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    scores: dict[str, float] = field(default_factory=dict)

    def add_transition(self, src: str, dst: str, score: float = 0.0) -> None:
        self.edges[src].append(dst)
        self.scores[f"{src}->{dst}"] = score

    def neighbors(self, node: str) -> list[str]:
        return list(self.edges.get(node, []))
