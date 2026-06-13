from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation

@dataclass(slots=True)
class TrendPoint:
    index: int
    user_tokens: int
    assistant_tokens: int
    rolling_user: float
    rolling_assistant: float

def rolling_average(values: list[int], window: int) -> list[float]:
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i-window+1):i+1]
        out.append(sum(chunk) / len(chunk))
    return out

def conversation_output_trend(conv: Conversation, window: int = 7) -> list[TrendPoint]:
    user = [m.token_count() if m.role == "user" else 0 for m in conv.messages]
    assistant = [m.token_count() if m.role == "assistant" else 0 for m in conv.messages]
    ru, ra = rolling_average(user, window), rolling_average(assistant, window)
    return [TrendPoint(i, user[i], assistant[i], ru[i], ra[i]) for i in range(len(user))]
