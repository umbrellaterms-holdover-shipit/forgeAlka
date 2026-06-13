from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class ParsedQuery:
    terms: list[str]
    phrases: list[str]
    required: list[str]
    excluded: list[str]


def parse_query(query: str) -> ParsedQuery:
    import shlex
    parts = shlex.split(query)
    terms, phrases, required, excluded = [], [], [], []
    for part in parts:
        target = terms
        raw = part
        if part.startswith("+"):
            target = required
            raw = part[1:]
        elif part.startswith("-"):
            target = excluded
            raw = part[1:]
        if " " in raw:
            phrases.append(raw)
        else:
            target.append(raw)
    return ParsedQuery(terms, phrases, required, excluded)
