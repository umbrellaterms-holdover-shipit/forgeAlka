"""Postings list implementation.

This module defines a class for an inverted index mapping term IDs to
lists of message identifiers where the term occurs. It is a minimal
structure suitable for demonstration purposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Iterable


@dataclass
class PostingsIndex:
    """Inverted index mapping term IDs to message IDs."""

    index: Dict[int, List[str]] = field(default_factory=dict)

    def add(self, term_id: int, message_id: str) -> None:
        self.index.setdefault(term_id, []).append(message_id)

    def get(self, term_id: int) -> List[str]:
        return self.index.get(term_id, [])