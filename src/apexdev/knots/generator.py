from __future__ import annotations
from dataclasses import dataclass
import random
from ..core.models import Conversation, Message
from ..indexes.tokenizer import tokenize

QUESTION_MARKERS = ["why", "how", "what", "where", "when", "isn't", "doesn't", "can't", "?"]

@dataclass(slots=True)
class Knot:
    seed_message_id: str
    caught_message_id: str | None
    question: str
    evidence_ids: list[str]
    echo_terms: list[str]

def catches_question(text: str) -> bool:
    lower = text.lower()
    return "?" in text or any(lower.startswith(m + " ") for m in QUESTION_MARKERS)

def local_echo_terms(messages: list[Message], center: int, radius: int = 3) -> list[str]:
    start, end = max(0, center - radius), min(len(messages), center + radius + 1)
    counts = {}
    for m in messages[start:end]:
        for tok in tokenize(m.content):
            if len(tok) > 4:
                counts[tok] = counts.get(tok, 0) + 1
    return [t for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]

def render_question(terms: list[str], message: Message) -> str:
    if terms:
        return f"What changes if we follow the echo between {', '.join(terms[:3])} instead of the surface topic?"
    return f"What is the local unresolved question around message {message.id}?"

def generate_knot(conversation: Conversation, seed: int = 0, max_forward: int = 12) -> Knot:
    if not conversation.messages:
        return Knot("", None, "What is missing from the empty conversation?", [], [])
    rng = random.Random(seed)
    start = rng.randrange(len(conversation.messages))
    caught = None
    for idx in range(start, min(len(conversation.messages), start + max_forward)):
        if catches_question(conversation.messages[idx].content):
            caught = idx; break
    if caught is None:
        caught = min(len(conversation.messages) - 1, start + max_forward - 1)
    terms = local_echo_terms(conversation.messages, caught)
    evidence = [m.id for m in conversation.messages[max(0, caught-3): min(len(conversation.messages), caught+4)]]
    return Knot(conversation.messages[start].id, conversation.messages[caught].id, render_question(terms, conversation.messages[caught]), evidence, terms)
