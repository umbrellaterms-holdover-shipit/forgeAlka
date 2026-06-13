from __future__ import annotations
import re

def strip_frontmatter(markdown: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", markdown, flags=re.S)

def markdown_word_count(markdown: str) -> int:
    body = strip_frontmatter(re.sub(r"`{3}.*?`{3}", "", markdown, flags=re.S))
    return len(re.findall(r"\b[\w']+\b", body))

def heading_outline(markdown: str) -> list[tuple[int, str]]:
    out = []
    for line in markdown.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out
