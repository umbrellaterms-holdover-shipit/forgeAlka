from __future__ import annotations
from collections import Counter, defaultdict
from ..core.models import Conversation

def role_counts(conversations: list[Conversation]) -> dict[str, int]:
    return dict(Counter(m.role for conv in conversations for m in conv.messages))

def role_token_counts(conversations: list[Conversation]) -> dict[str, int]:
    c = Counter()
    for conv in conversations:
        for msg in conv.messages:
            c[msg.role] += msg.token_count()
    return dict(c)

def daily_role_tokens(conversations: list[Conversation]) -> dict[str, dict[str, int]]:
    out = defaultdict(Counter)
    for conv in conversations:
        for msg in conv.messages:
            day = str(int((msg.create_time or conv.create_time or 0) // 86400))
            out[day][msg.role] += msg.token_count()
    return {k: dict(v) for k, v in out.items()}
