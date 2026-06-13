from __future__ import annotations
from ..core.models import Conversation, Message

def neighbor(conversation: Conversation, message_id: str, offset: int) -> Message | None:
    ids = [m.id for m in conversation.messages]
    try:
        idx = ids.index(message_id)
    except ValueError:
        return None
    target = idx + offset
    return conversation.messages[target] if 0 <= target < len(conversation.messages) else None

def walk(conversation: Conversation, start_id: str, steps: int) -> list[Message]:
    ids = [m.id for m in conversation.messages]
    try:
        idx = ids.index(start_id)
    except ValueError:
        return []
    if steps >= 0:
        return conversation.messages[idx:min(len(conversation.messages), idx+steps+1)]
    return conversation.messages[max(0, idx+steps):idx+1]
