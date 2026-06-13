from __future__ import annotations
from pathlib import Path
from ..core.loader import load_conversations
from ..core.models import Conversation


def load_shard(path: str | Path, active_only: bool = False) -> list[Conversation]:
    conversations = load_conversations(path)
    if not active_only:
        return conversations
    from .active_path import filter_to_active_path
    return [filter_to_active_path(c) for c in conversations]
