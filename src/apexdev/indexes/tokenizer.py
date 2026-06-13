from __future__ import annotations
import re
TOKEN_RE = re.compile(r"[A-Za-z0-9_']+")
def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]
