"""Utilities for converting conversations to Markdown.

This module provides simple functions for serialising conversations
into human-readable Markdown documents.  Each message is rendered
with a prefix indicating the role (e.g. **User:**) and the content
as-is.  Code blocks within the content are preserved.  You can
extend this module to include more advanced formatting, such as
tables of contents or metadata sections.
"""

from __future__ import annotations

from typing import Iterable, List

from ..core.models import Conversation, Message


def message_to_markdown(message: Message) -> str:
    """Convert a single message to markdown format.

    Parameters
    ----------
    message:
        The message to convert.

    Returns
    -------
    str
        A markdown-formatted representation of the message.
    """
    role = message.role.capitalize() if message.role else 'Message'
    content = message.content or ''
    return f"**{role}:**\n\n{content}\n\n"


def conversation_to_markdown(conversation: Conversation) -> str:
    """Serialise an entire conversation to markdown.

    Parameters
    ----------
    conversation:
        A Conversation instance.

    Returns
    -------
    str
        A markdown document representing the conversation.
    """
    parts: List[str] = []
    title = conversation.title or 'Conversation'
    parts.append(f"# {title}\n\n")
    for msg in conversation.messages:
        parts.append(message_to_markdown(msg))
    return ''.join(parts)


def conversations_to_markdown(conversations: Iterable[Conversation]) -> str:
    """Serialise multiple conversations to a single markdown string.

    Parameters
    ----------
    conversations:
        Iterable of Conversation instances.

    Returns
    -------
    str
        Markdown-formatted string containing all conversations.
    """
    docs: List[str] = []
    for convo in conversations:
        docs.append(conversation_to_markdown(convo))
    return '\n\n'.join(docs)