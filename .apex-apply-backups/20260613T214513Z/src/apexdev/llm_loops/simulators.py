from __future__ import annotations

def rejection_simulator(response: str, forbidden_terms: list[str] | None = None) -> tuple[bool, float]:
    forbidden_terms = forbidden_terms or []
    lower = response.lower()
    penalty = sum(1 for term in forbidden_terms if term.lower() in lower)
    return penalty == 0, max(0.0, 1.0 - 0.25 * penalty)
