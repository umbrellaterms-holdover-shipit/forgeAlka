from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .models import Conversation, Message


def _extract_text(content: Any) -> tuple[str, str]:
    if isinstance(content, str):
        return content, "text"
    if isinstance(content, dict):
        ctype = content.get("content_type") or content.get("type") or "text"
        if isinstance(content.get("text"), str):
            return content["text"], ctype
        if isinstance(content.get("content"), str):
            return content["content"], ctype
        parts = content.get("parts")
        if isinstance(parts, list):
            out = []
            for part in parts:
                if isinstance(part, str):
                    out.append(part)
                elif isinstance(part, dict):
                    out.append(str(part.get("text") or part.get("content") or ""))
            return "\n".join(x for x in out if x), ctype
    return "", "text"


def load_conversations(path: str | Path) -> list[Conversation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "conversations" in data:
        data = data["conversations"]
    if isinstance(data, dict):
        data = [data]
    return [_load_conversation(obj) for obj in data]


def _load_conversation(obj: dict[str, Any]) -> Conversation:
    cid = str(obj.get("conversation_id") or obj.get("id") or "conversation")
    conv = Conversation(
        id=cid,
        title=obj.get("title") or "",
        source_file=obj.get("source_file"),
        create_time=obj.get("create_time"),
        update_time=obj.get("update_time"),
        metadata={k: v for k, v in obj.items() if k not in {"messages", "mapping"}},
    )
    if isinstance(obj.get("messages"), list):
        for i, m in enumerate(obj["messages"]):
            raw = m.get("text") if "text" in m else m.get("content", "")
            text, ctype = _extract_text(raw)
            conv.messages.append(Message(
                id=str(m.get("node_id") or m.get("id") or m.get("message_id") or f"{cid}:{i}"),
                parent_id=m.get("parent") or m.get("parent_id"),
                role=str(m.get("role") or m.get("author", {}).get("role") or "unknown"),
                content=text,
                create_time=m.get("create_time"),
                content_type=str(m.get("content_type") or ctype),
                conversation_id=cid,
                title=conv.title,
                source_file=conv.source_file,
                ordinal=i,
                metadata={k: v for k, v in m.items() if k not in {"text", "content"}},
            ))
    elif isinstance(obj.get("mapping"), dict):
        nodes = list(obj["mapping"].values())
        nodes.sort(key=lambda n: ((n.get("message") or {}).get("create_time") is None, (n.get("message") or {}).get("create_time") or 0))
        for i, node in enumerate(nodes):
            msgobj = node.get("message")
            if not msgobj:
                continue
            author = msgobj.get("author") or {}
            text, ctype = _extract_text(msgobj.get("content", {}))
            if not text:
                continue
            conv.messages.append(Message(
                id=str(node.get("id") or msgobj.get("id") or f"{cid}:{i}"),
                parent_id=node.get("parent"),
                role=str(author.get("role") or "unknown"),
                content=text,
                create_time=msgobj.get("create_time"),
                content_type=ctype,
                conversation_id=cid,
                title=conv.title,
                source_file=conv.source_file,
                ordinal=i,
                metadata={"children": node.get("children", [])},
            ))
    return conv


def dump_conversations(conversations: list[Conversation], path: str | Path) -> None:
    Path(path).write_text(json.dumps([c.to_dict() for c in conversations], indent=2, ensure_ascii=False), encoding="utf-8")
