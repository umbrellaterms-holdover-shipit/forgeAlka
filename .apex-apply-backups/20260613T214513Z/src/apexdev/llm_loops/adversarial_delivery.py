from __future__ import annotations
from .adapters import LLMAdapter, DummyAdapter
from .payload_graph import PayloadGraph
from .simulators import rejection_simulator

def run_payload_loop(payloads: list[str], adapter: LLMAdapter | None = None, forbidden_terms: list[str] | None = None) -> PayloadGraph:
    adapter = adapter or DummyAdapter()
    graph = PayloadGraph()
    last = "start"
    for payload in payloads:
        response = adapter.generate(payload)
        accepted, score = rejection_simulator(response, forbidden_terms)
        node = f"accepted:{payload[:24]}" if accepted else f"rejected:{payload[:24]}"
        graph.add_transition(last, node, score)
        last = node
    return graph
