from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
from ..core.models import Message

@dataclass(slots=True)
class Fragment:
    id: str
    conversation_id: str
    message_id: str
    title: str
    role: str
    content_type: str
    text: str
    operations: list[str] = field(default_factory=list)
    hot_attractors: list[str] = field(default_factory=list)
    side_markers: list[str] = field(default_factory=list)
    score: float = 0.0
    reason_codes: list[str] = field(default_factory=list)

    @classmethod
    def from_message(cls, msg: Message, text: str | None = None) -> "Fragment":
        body = text if text is not None else msg.content
        fid = hashlib.sha1(f"{msg.conversation_id}:{msg.id}:{body[:80]}".encode("utf-8", "ignore")).hexdigest()[:16]
        return cls(f"frag_{fid}", msg.conversation_id or "", msg.id, msg.title or "", msg.role, msg.content_type, body)
