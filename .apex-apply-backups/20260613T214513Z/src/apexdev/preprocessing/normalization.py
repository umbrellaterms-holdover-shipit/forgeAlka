from __future__ import annotations
import re
import unicodedata

WHITESPACE_RE = re.compile(r"\s+")

def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n"))
    return text.strip()

def normalize_title(title: str) -> str:
    return re.sub(r"[^\w .·-]+", "", normalize_text(title))[:120]

def normalize_role(role: str) -> str:
    role = (role or "unknown").lower().strip()
    aliases = {"assistant_tool": "tool", "model": "assistant", "human": "user"}
    return aliases.get(role, role)
