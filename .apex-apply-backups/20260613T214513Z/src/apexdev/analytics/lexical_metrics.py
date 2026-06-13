from __future__ import annotations
from collections import Counter
import re
TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")

def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]

def type_token_ratio(text: str) -> float:
    ts = tokens(text)
    return len(set(ts)) / len(ts) if ts else 0.0

def moving_ttr(texts: list[str], window: int = 5) -> list[float]:
    vals = []
    for i in range(len(texts)):
        vals.append(type_token_ratio("\n".join(texts[max(0, i-window+1):i+1])))
    return vals

def top_terms(text: str, n: int = 20, stopwords: set[str] | None = None) -> list[tuple[str, int]]:
    stopwords = stopwords or {"the", "a", "an", "and", "or", "to", "of", "in", "it", "is", "that", "this"}
    return Counter(t for t in tokens(text) if t not in stopwords and len(t) > 2).most_common(n)
