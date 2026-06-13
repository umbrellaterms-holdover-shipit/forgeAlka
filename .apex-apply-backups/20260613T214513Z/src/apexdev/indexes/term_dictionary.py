"""Term dictionary for indexing.

This module implements a simple term dictionary that assigns
incrementing integer IDs to tokens. It is used by the postings
implementation to build an inverted index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class TermDictionary:
    """Map tokens to integer IDs and back."""

    token_to_id: Dict[str, int] = field(default_factory=dict)
    id_to_token: Dict[int, str] = field(default_factory=dict)

    def get_id(self, token: str) -> int:
        if token not in self.token_to_id:
            new_id = len(self.token_to_id)
            self.token_to_id[token] = new_id
            self.id_to_token[new_id] = token
        return self.token_to_id[token]

    def get_token(self, id_: int) -> str:
        return self.id_to_token.get(id_, "")