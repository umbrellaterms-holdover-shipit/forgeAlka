from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import math
from typing import Iterable
from .tokenizer import tokenize


@dataclass(slots=True)
class SearchDocument:
    id: str
    text: str
    metadata: dict


@dataclass
class SearchIndex:
    documents: dict[str, SearchDocument] = field(default_factory=dict)
    term_freqs: dict[str, Counter[str]] = field(default_factory=dict)
    doc_freqs: Counter[str] = field(default_factory=Counter)
    doc_lengths: dict[str, int] = field(default_factory=dict)
    avg_len: float = 0.0

    def add(self, doc: SearchDocument) -> None:
        if doc.id in self.documents:
            self.remove(doc.id)
        terms = tokenize(doc.text)
        freqs = Counter(terms)
        self.documents[doc.id] = doc
        self.term_freqs[doc.id] = freqs
        self.doc_lengths[doc.id] = len(terms)
        for term in freqs:
            self.doc_freqs[term] += 1
        self._refresh_avg_len()

    def remove(self, doc_id: str) -> None:
        freqs = self.term_freqs.pop(doc_id, Counter())
        for term in freqs:
            self.doc_freqs[term] -= 1
            if self.doc_freqs[term] <= 0:
                del self.doc_freqs[term]
        self.documents.pop(doc_id, None)
        self.doc_lengths.pop(doc_id, None)
        self._refresh_avg_len()

    def _refresh_avg_len(self) -> None:
        self.avg_len = sum(self.doc_lengths.values()) / max(1, len(self.doc_lengths))

    def search(self, query: str, limit: int = 10) -> list[tuple[SearchDocument, float]]:
        qterms = tokenize(query)
        if not qterms:
            return []
        scores: dict[str, float] = defaultdict(float)
        n_docs = max(1, len(self.documents))
        k1 = 1.5
        b = 0.75
        for term in qterms:
            df = self.doc_freqs.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for doc_id, freqs in self.term_freqs.items():
                tf = freqs.get(term, 0)
                if not tf:
                    continue
                length = self.doc_lengths.get(doc_id, 0)
                denom = tf + k1 * (1 - b + b * length / max(1e-9, self.avg_len))
                scores[doc_id] += idf * (tf * (k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [(self.documents[doc_id], score) for doc_id, score in ranked]

    def to_dict(self) -> dict:
        return {
            "documents": {k: {"text": v.text, "metadata": v.metadata} for k, v in self.documents.items()},
            "doc_freqs": dict(self.doc_freqs),
            "doc_lengths": self.doc_lengths,
            "avg_len": self.avg_len,
        }


def build_search_index(docs: Iterable[SearchDocument]) -> SearchIndex:
    idx = SearchIndex()
    for doc in docs:
        idx.add(doc)
    return idx
