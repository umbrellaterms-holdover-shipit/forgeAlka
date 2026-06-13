from __future__ import annotations
from dataclasses import dataclass
from ..core.loader import load_conversations
from ..core.models import Conversation
from .dedupe import dedupe_messages
from .normalization import normalize_text, normalize_role, normalize_title


@dataclass(slots=True)
class PreprocessResult:
    conversations: list[Conversation]
    dropped_message_ids: list[str]


def preprocess_file(path: str, *, dedupe: bool = True) -> PreprocessResult:
    conversations = load_conversations(path)
    for conv in conversations:
        conv.title = normalize_title(conv.title)
        for msg in conv.messages:
            msg.role = normalize_role(msg.role)
            msg.content = normalize_text(msg.content)
    if dedupe:
        result = dedupe_messages(conversations)
        return PreprocessResult(result.conversations, result.dropped_message_ids)
    return PreprocessResult(conversations, [])
