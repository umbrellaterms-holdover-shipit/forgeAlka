from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation, Message


@dataclass(slots=True)
class ConversationChunk:
    id: str
    conversation_id: str
    title: str
    start_ordinal: int
    end_ordinal: int
    messages: list[Message]

    def text(self) -> str:
        return "\n\n".join(f"{m.role}: {m.content}" for m in self.messages)


def split_by_tokens(conversation: Conversation, max_tokens: int = 1200, overlap_messages: int = 1) -> list[ConversationChunk]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    chunks: list[ConversationChunk] = []
    current: list[Message] = []
    current_tokens = 0
    start = 0
    for msg in conversation.messages:
        t = msg.token_count()
        if current and current_tokens + t > max_tokens:
            end = current[-1].ordinal
            chunks.append(ConversationChunk(f"{conversation.id}:chunk:{len(chunks)}", conversation.id, conversation.title, start, end, list(current)))
            current = current[-overlap_messages:] if overlap_messages else []
            current_tokens = sum(m.token_count() for m in current)
            start = current[0].ordinal if current else msg.ordinal
        current.append(msg)
        current_tokens += t
    if current:
        chunks.append(ConversationChunk(f"{conversation.id}:chunk:{len(chunks)}", conversation.id, conversation.title, start, current[-1].ordinal, list(current)))
    return chunks


def split_many(conversations: list[Conversation], max_tokens: int = 1200) -> list[ConversationChunk]:
    out: list[ConversationChunk] = []
    for conv in conversations:
        out.extend(split_by_tokens(conv, max_tokens=max_tokens))
    return out
