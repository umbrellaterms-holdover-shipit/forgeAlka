from __future__ import annotations
from typing import Protocol

class LLMAdapter(Protocol):
    def generate(self, prompt: str, **kwargs) -> str: ...

class DummyAdapter:
    def generate(self, prompt: str, **kwargs) -> str:
        return f"[dummy-response]\n{prompt[:1000]}"
