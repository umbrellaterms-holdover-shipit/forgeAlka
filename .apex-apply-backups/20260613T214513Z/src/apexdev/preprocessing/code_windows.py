from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation, Message
from ..code_inspection.code_signal_detector import detect_code_signal


@dataclass(slots=True)
class CodeWindow:
    conversation_id: str
    center_message_id: str
    start_ordinal: int
    end_ordinal: int
    messages: list[Message]
    score: float


def extract_code_windows(conversations: list[Conversation], radius: int = 2, min_score: float = 5.0) -> list[CodeWindow]:
    windows: list[CodeWindow] = []
    for conv in conversations:
        for i, msg in enumerate(conv.messages):
            sig = detect_code_signal(msg.content, msg.content_type)
            if sig.score < min_score:
                continue
            start = max(0, i - radius)
            end = min(len(conv.messages), i + radius + 1)
            windows.append(CodeWindow(conv.id, msg.id, start, end - 1, conv.messages[start:end], sig.score))
    return windows
