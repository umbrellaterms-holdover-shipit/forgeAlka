from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation

@dataclass(slots=True)
class Spine:
    conversation_id: str
    title: str
    message_ids: list[str]

    def windows(self, size: int) -> list[list[str]]:
        if size <= 0:
            raise ValueError("window size must be positive")
        return [self.message_ids[i:i+size] for i in range(max(0, len(self.message_ids)-size+1))]

def build_spines(conversations: list[Conversation]) -> list[Spine]:
    return [Spine(c.id, c.title, [m.id for m in c.messages]) for c in conversations]

def build_turn_index(conversations: list[Conversation]) -> dict[str, dict]:
    rows = {}
    for conv in conversations:
        for i, msg in enumerate(conv.messages):
            rows[msg.id] = {"conversation_id": conv.id, "title": conv.title, "ordinal": i, "role": msg.role}
    return rows
