"""State objects for the noticing engine.

The noticing engine may maintain state across multiple runs. This
module provides a simple state container that keeps track of seen
fragments and sampling seeds. Persisting state can help ensure that
the engine does not repeatedly select the same fragments in successive
packets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set


@dataclass
class NoticingState:
    """State for the noticing engine."""

    seen_fragment_ids: Set[str] = field(default_factory=set)

    def mark_seen(self, fragment_id: str) -> None:
        self.seen_fragment_ids.add(fragment_id)

    def has_seen(self, fragment_id: str) -> bool:
        return fragment_id in self.seen_fragment_ids