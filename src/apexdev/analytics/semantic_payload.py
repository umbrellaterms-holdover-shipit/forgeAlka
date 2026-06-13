from __future__ import annotations
from ..core.models import Conversation, Message

CONTENT_WEIGHTS = {"text": 1.0, "thoughts": 1.25, "reasoning_recap": 1.15, "multimodal_text": 1.35}

def message_payload(msg: Message) -> float:
    words = msg.token_count()
    unique = len(set(msg.content.lower().split()))
    density = unique / max(1, words)
    content_weight = CONTENT_WEIGHTS.get(msg.content_type, 1.0)
    structure_bonus = min(1.0, (msg.content.count(":") + msg.content.count("→") + msg.content.count('"')) / 20)
    return round((words * (0.5 + density) * content_weight) + structure_bonus, 4)

def conversation_payload(conv: Conversation) -> float:
    return round(sum(message_payload(m) for m in conv.messages), 4)

def corpus_payload(conversations: list[Conversation]) -> dict[str, float]:
    return {conv.id: conversation_payload(conv) for conv in conversations}
