from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation, Message


@dataclass(slots=True)
class ActivePath:
    conversation_id: str
    title: str
    message_ids: list[str]

    def contains(self, message_id: str) -> bool:
        return message_id in self.message_ids


def infer_active_path(conversation: Conversation) -> ActivePath:
    """Infer an active path from parent pointers.

    If parent pointers are present, this follows the deepest leaf back to
    root. If not, it falls back to chronological message order.
    """
    if not conversation.messages:
        return ActivePath(conversation.id, conversation.title, [])

    by_id = {m.id: m for m in conversation.messages}
    children: dict[str, list[str]] = {m.id: [] for m in conversation.messages}
    for m in conversation.messages:
        if m.parent_id and m.parent_id in children:
            children[m.parent_id].append(m.id)

    if not any(children.values()):
        return ActivePath(conversation.id, conversation.title, [m.id for m in conversation.messages])

    depth_cache: dict[str, int] = {}

    def depth(mid: str) -> int:
        if mid in depth_cache:
            return depth_cache[mid]
        m = by_id[mid]
        if not m.parent_id or m.parent_id not in by_id:
            depth_cache[mid] = 0
        else:
            depth_cache[mid] = 1 + depth(m.parent_id)
        return depth_cache[mid]

    leaves = [m.id for m in conversation.messages if not children.get(m.id)]
    leaf = max(leaves, key=lambda mid: (depth(mid), by_id[mid].ordinal))
    path: list[str] = []
    current: str | None = leaf
    while current and current in by_id:
        path.append(current)
        current = by_id[current].parent_id
    path.reverse()
    return ActivePath(conversation.id, conversation.title, path)


def filter_to_active_path(conversation: Conversation) -> Conversation:
    path = infer_active_path(conversation)
    keep = set(path.message_ids)
    clone = Conversation(
        id=conversation.id,
        title=conversation.title,
        source_file=conversation.source_file,
        create_time=conversation.create_time,
        update_time=conversation.update_time,
        metadata=dict(conversation.metadata),
    )
    clone.messages = [m for m in conversation.messages if m.id in keep]
    return clone
