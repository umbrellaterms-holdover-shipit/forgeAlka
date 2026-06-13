from __future__ import annotations
from dataclasses import dataclass, field
import re

CODE_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
SHELL_RE = re.compile(r"^\s*(python|pip|uv|npm|node|git|make|cmake|pytest|ffmpeg|curl)\b", re.M)
CODE_LINE_RE = re.compile(r"^\s*(def |class |import |from |for |while |if __name__|#include|int main|function |const |let |var )", re.M)
REASONING_TERMS = ["use python", "write a script", "generate a report", "create a file", "make a zip", "run pytest", "parse json", "use jinja", "build package"]


@dataclass(slots=True)
class CodeSignal:
    has_fence: bool = False
    fence_count: int = 0
    inline_count: int = 0
    shell_count: int = 0
    code_line_count: int = 0
    reasoning_intent: bool = False
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


def detect_code_signal(text: str, content_type: str = "text") -> CodeSignal:
    sig = CodeSignal()
    sig.fence_count = len(CODE_FENCE_RE.findall(text))
    sig.has_fence = sig.fence_count > 0
    sig.inline_count = len(INLINE_CODE_RE.findall(text))
    sig.shell_count = len(SHELL_RE.findall(text))
    sig.code_line_count = len(CODE_LINE_RE.findall(text))
    lower = text.lower()
    sig.reasoning_intent = content_type in {"thoughts", "reasoning_recap"} and any(t in lower for t in REASONING_TERMS)
    if sig.fence_count:
        sig.score += sig.fence_count * 5
        sig.reasons.append(f"fenced:{sig.fence_count}")
    if sig.inline_count:
        sig.score += min(sig.inline_count, 10) * 0.5
        sig.reasons.append(f"inline:{sig.inline_count}")
    if sig.shell_count:
        sig.score += sig.shell_count * 2
        sig.reasons.append(f"shell:{sig.shell_count}")
    if sig.code_line_count:
        sig.score += sig.code_line_count * 1.5
        sig.reasons.append(f"code_lines:{sig.code_line_count}")
    if sig.reasoning_intent:
        sig.score += 3
        sig.reasons.append("reasoning_intent")
    return sig
