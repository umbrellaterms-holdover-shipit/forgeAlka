from __future__ import annotations
from dataclasses import dataclass
import hashlib
from ..core.models import Conversation, Message


def content_hash(text: str, prefix_len: int = 1200) -> str:
    return hashlib.sha1(text[:prefix_len].encode("utf-8", "ignore")).hexdigest()


@dataclass(slots=True)
class DedupeResult:
    conversations: list[Conversation]
    dropped_message_ids: list[str]


def dedupe_messages(conversations: list[Conversation]) -> DedupeResult:
    seen: set[tuple[str, str, str]] = set()
    dropped: list[str] = []
    out: list[Conversation] = []
    for conv in conversations:
        clone = Conversation(
            id=conv.id,
            title=conv.title,
            source_file=conv.source_file,
            create_time=conv.create_time,
            update_time=conv.update_time,
            metadata=dict(conv.metadata),
        )
        for msg in conv.messages:
            key = (msg.role, msg.content_type, content_hash(msg.content))
            if key in seen:
                dropped.append(msg.id)
                continue
            seen.add(key)
            clone.messages.append(msg)
        out.append(clone)
    return DedupeResult(out, dropped)
