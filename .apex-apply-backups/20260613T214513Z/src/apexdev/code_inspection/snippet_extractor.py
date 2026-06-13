from __future__ import annotations
from dataclasses import dataclass
from .code_signal_detector import CODE_FENCE_RE, INLINE_CODE_RE, SHELL_RE


@dataclass(slots=True)
class Snippet:
    kind: str
    text: str
    language: str = ""
    start: int = 0
    end: int = 0


def extract_snippets(text: str) -> list[Snippet]:
    out: list[Snippet] = []
    for m in CODE_FENCE_RE.finditer(text):
        out.append(Snippet("fenced", m.group(2).strip(), m.group(1) or "", m.start(), m.end()))
    for m in INLINE_CODE_RE.finditer(text):
        out.append(Snippet("inline", m.group(1).strip(), "", m.start(), m.end()))
    for m in SHELL_RE.finditer(text):
        start = text.rfind("\n", 0, m.start()) + 1
        end = text.find("\n", m.end())
        if end == -1:
            end = len(text)
        out.append(Snippet("shell", text[start:end].strip(), "bash", start, end))
    return out
