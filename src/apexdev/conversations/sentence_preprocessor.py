from __future__ import annotations
from dataclasses import dataclass
import re
from ..core.models import Conversation


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])")


@dataclass(slots=True)
class SentenceRecord:
    sentence_id: str
    conversation_id: str
    message_id: str
    role: str
    ordinal: int
    sentence_index: int
    text: str


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    return [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]


def preprocess_sentences(conversations: list[Conversation]) -> list[SentenceRecord]:
    rows: list[SentenceRecord] = []
    for conv in conversations:
        for msg in conv.messages:
            for idx, sentence in enumerate(split_sentences(msg.content)):
                sid = f"{msg.id}:s{idx}"
                rows.append(SentenceRecord(sid, conv.id, msg.id, msg.role, msg.ordinal, idx, sentence))
    return rows


def to_tsv(rows: list[SentenceRecord]) -> str:
    lines = ["sentence_id\tconversation_id\tmessage_id\trole\tordinal\tsentence_index\ttext"]
    for r in rows:
        text = r.text.replace("\t", " ").replace("\n", " ")
        lines.append(f"{r.sentence_id}\t{r.conversation_id}\t{r.message_id}\t{r.role}\t{r.ordinal}\t{r.sentence_index}\t{text}")
    return "\n".join(lines) + "\n"
