from __future__ import annotations
from dataclasses import dataclass, field
from ..core.models import Conversation
from .engine import generate_packet
from .config import NoticingConfig

@dataclass(slots=True)
class EvidencePack:
    name: str
    conversations: list[Conversation]
    expected_operation_terms: list[str] = field(default_factory=list)
    expected_fragment_terms: list[str] = field(default_factory=list)

@dataclass(slots=True)
class BenchmarkResult:
    name: str
    operation_hit: bool
    fragment_hits: int
    expected_fragment_terms: int
    precision_like: float
    recall_like: float

def run_pack(pack: EvidencePack, config: NoticingConfig | None = None) -> BenchmarkResult:
    packet = generate_packet(pack.conversations, config)
    op = packet["operation"].lower()
    operation_hit = not pack.expected_operation_terms or any(t.lower() in op for t in pack.expected_operation_terms)
    selected_text = "\n".join(f["text"].lower() for f in packet["fragments"])
    hits = sum(1 for term in pack.expected_fragment_terms if term.lower() in selected_text)
    expected = len(pack.expected_fragment_terms)
    return BenchmarkResult(pack.name, operation_hit, hits, expected, hits / max(1, len(packet["fragments"])), hits / max(1, expected))

def render_benchmark_report(results: list[BenchmarkResult]) -> str:
    lines = ["# Noticing Benchmark Report", ""]
    for r in results:
        lines += [f"## {r.name}", f"- operation_hit: {r.operation_hit}", f"- fragment_hits: {r.fragment_hits}/{r.expected_fragment_terms}", f"- precision_like: {r.precision_like:.3f}", f"- recall_like: {r.recall_like:.3f}", ""]
    return "\n".join(lines)
