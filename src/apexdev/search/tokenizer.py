from __future__ import annotations
import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")

DEFAULT_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "it", "this", "that", "as", "be", "by", "from",
}

def tokenize(text: str, *, stopwords: set[str] | None = None) -> list[str]:
    stopwords = DEFAULT_STOPWORDS if stopwords is None else stopwords
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in stopwords]

def shingles(tokens: list[str], n: int = 3) -> set[tuple[str, ...]]:
    if n <= 0:
        raise ValueError("n must be positive")
    if len(tokens) < n:
        return set()
    return {tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)}
