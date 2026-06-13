from __future__ import annotations
from dataclasses import dataclass
from ..core.models import Conversation

CORRECTION_MARKERS = ["no.", "not quite", "wrong", "you missed", "that's not", "actually", "correction"]
ACCEPTANCE_MARKERS = ["yes.", "exactly", "good.", "dead on", "that's right", "this works", "excellent"]

@dataclass(slots=True)
class TurnSignal:
    kind: str
    message_id: str
    conversation_id: str
    marker: str
    content: str

def detect_turn_signals(conversations: list[Conversation]) -> list[TurnSignal]:
    signals = []
    for conv in conversations:
        for msg in conv.messages:
            if msg.role != "user":
                continue
            lower = msg.content.lower()
            for marker in CORRECTION_MARKERS:
                if marker in lower:
                    signals.append(TurnSignal("correction", msg.id, conv.id, marker, msg.content)); break
            for marker in ACCEPTANCE_MARKERS:
                if marker in lower:
                    signals.append(TurnSignal("acceptance", msg.id, conv.id, marker, msg.content)); break
    return signals

def detect_artifact_requests(conversations: list[Conversation]) -> list[TurnSignal]:
    markers = ["zip", "pdf", "docx", "xlsx", "markdown", "chart", "spreadsheet", "slides", "package"]
    out = []
    for conv in conversations:
        for msg in conv.messages:
            lower = msg.content.lower()
            if msg.role == "user":
                for marker in markers:
                    if marker in lower:
                        out.append(TurnSignal("artifact_request", msg.id, conv.id, marker, msg.content)); break
    return out
