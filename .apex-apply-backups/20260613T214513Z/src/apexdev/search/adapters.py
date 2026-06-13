from __future__ import annotations
from ..core.models import Conversation
from .index import SearchDocument


def conversation_documents(conversations: list[Conversation]) -> list[SearchDocument]:
    docs = []
    for conv in conversations:
        for msg in conv.messages:
            docs.append(SearchDocument(
                id=msg.id,
                text=msg.content,
                metadata={
                    "conversation_id": conv.id,
                    "title": conv.title,
                    "role": msg.role,
                    "ordinal": msg.ordinal,
                    "content_type": msg.content_type,
                },
            ))
    return docs


def chunk_documents(chunks) -> list[SearchDocument]:
    docs = []
    for chunk in chunks:
        docs.append(SearchDocument(
            id=chunk.id,
            text=chunk.text(),
            metadata={
                "conversation_id": chunk.conversation_id,
                "title": chunk.title,
                "start_ordinal": chunk.start_ordinal,
                "end_ordinal": chunk.end_ordinal,
            },
        ))
    return docs
