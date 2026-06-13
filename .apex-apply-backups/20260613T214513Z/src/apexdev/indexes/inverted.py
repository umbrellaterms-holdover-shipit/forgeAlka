from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from ..core.models import Conversation, Message
from .tokenizer import tokenize

@dataclass
class InvertedIndex:
    postings: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    documents: dict[str, Message] = field(default_factory=dict)
    frequencies: dict[str, Counter[str]] = field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        self.documents[message.id] = message
        counts = Counter(tokenize(message.content))
        self.frequencies[message.id] = counts
        for token in counts:
            self.postings[token].add(message.id)

    def build(self, conversations: list[Conversation]) -> "InvertedIndex":
        for conv in conversations:
            for msg in conv.messages:
                self.add_message(msg)
        return self

    def search(self, query: str, mode: str = "and") -> list[Message]:
        terms = tokenize(query)
        if not terms:
            return []
        sets = [self.postings.get(t, set()) for t in terms]
        ids = set().union(*sets) if mode == "or" else (set.intersection(*sets) if sets else set())
        def score(mid: str) -> int:
            return sum(self.frequencies[mid].get(t, 0) for t in terms)
        return [self.documents[mid] for mid in sorted(ids, key=score, reverse=True)]
