from __future__ import annotations
import re
from dataclasses import dataclass
from ..core.models import Conversation

QUOTE_RE = re.compile(r'"([^"]{8,300})"|“([^”]{8,300})”|`([^`]{8,300})`')

@dataclass(slots=True)
class QuoteAnchor:
    quote: str
    quoting_message_id: str
    matched_message_ids: list[str]

def extract_quote_anchors(conversations: list[Conversation]) -> list[QuoteAnchor]:
    all_messages = [m for c in conversations for m in c.messages]
    anchors = []
    for msg in all_messages:
        for m in QUOTE_RE.finditer(msg.content):
            quote = next(g for g in m.groups() if g)
            matches = [other.id for other in all_messages if other.id != msg.id and quote.lower() in other.content.lower()]
            anchors.append(QuoteAnchor(quote, msg.id, matches))
    return anchors
