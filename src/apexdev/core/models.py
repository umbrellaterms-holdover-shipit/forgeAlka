from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable


@dataclass(slots=True)
class Message:
    id: str
    role: str
    content: str
    parent_id: str | None = None
    create_time: float | None = None
    content_type: str = "text"
    conversation_id: str | None = None
    title: str | None = None
    source_file: str | None = None
    ordinal: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def token_count(self) -> int:
        return len(self.content.split())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Conversation:
    id: str
    title: str = ""
    messages: list[Message] = field(default_factory=list)
    source_file: str | None = None
    create_time: float | None = None
    update_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def iter_messages(self, roles: set[str] | None = None) -> Iterable[Message]:
        for msg in self.messages:
            if roles is None or msg.role in roles:
                yield msg

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["messages"] = [m.to_dict() for m in self.messages]
        return d
