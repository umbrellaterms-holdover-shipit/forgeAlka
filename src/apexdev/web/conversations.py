from __future__ import annotations

"""Small JSON-file conversation store for the Apex web chat surface."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4
import json
import re
import tempfile

from apexdev.llm.preflight import estimate_message_tokens


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _message_id() -> str:
    return f"msg_{uuid4().hex}"


def _conversation_id() -> str:
    return f"conv_{uuid4().hex}"


def _clean_id(value: str) -> str:
    if not value or not _SAFE_ID_RE.match(value):
        raise ValueError(f"invalid conversation id: {value!r}")
    return value


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def normalize_message(message: Mapping[str, Any], *, now: str | None = None) -> dict[str, Any]:
    stamp = now or utc_now()
    role = str(message.get("role") or "user").strip() or "user"
    content = message.get("content", "")
    if not isinstance(content, (str, list)):
        content = str(content)
    message_id = str(message.get("id") or _message_id())
    created = str(message.get("created_at") or stamp)
    updated = str(message.get("updated_at") or created)
    row: dict[str, Any] = {
        "id": message_id,
        "role": role,
        "content": content,
        "created_at": created,
        "updated_at": updated,
    }
    meta = message.get("meta")
    if isinstance(meta, Mapping):
        row["meta"] = dict(meta)
    return row


def infer_title(messages: list[dict[str, Any]], fallback: str = "Untitled conversation") -> str:
    for message in messages:
        if message.get("role") == "user":
            text = _text_from_content(message.get("content")).strip().replace("\n", " ")
            if text:
                return text[:80]
    return fallback


def conversation_stats(messages: list[dict[str, Any]]) -> dict[str, Any]:
    text_parts = [_text_from_content(m.get("content")) for m in messages]
    text = "\n".join(text_parts)
    role_counts: dict[str, int] = {}
    for message in messages:
        role = str(message.get("role") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
    user_messages = role_counts.get("user", 0)
    assistant_messages = role_counts.get("assistant", 0)
    return {
        "messages": len(messages),
        "turns": min(user_messages, assistant_messages),
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "system_messages": role_counts.get("system", 0),
        "role_counts": role_counts,
        "characters": len(text),
        "words": len(text.split()),
        "estimated_tokens": estimate_message_tokens(messages),
    }


@dataclass
class ConversationStore:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, conversation_id: str) -> Path:
        return self.root / f"{_clean_id(conversation_id)}.json"

    def exists(self, conversation_id: str) -> bool:
        return self.path_for(conversation_id).exists()

    def list(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                rows.append(self.summary(self.load(path.stem)))
            except Exception:
                continue
        rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
        return rows

    def create(
        self,
        *,
        title: str | None = None,
        model: str | None = None,
        wire_format: str | None = None,
        messages: list[Mapping[str, Any]] | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        stamp = utc_now()
        normalized = [normalize_message(m, now=stamp) for m in (messages or [])]
        cid = conversation_id or _conversation_id()
        data: dict[str, Any] = {
            "id": cid,
            "title": (title or infer_title(normalized)).strip() or "Untitled conversation",
            "created_at": stamp,
            "updated_at": stamp,
            "model": model,
            "wire_format": wire_format or "auto",
            "messages": normalized,
        }
        return self.save(data)

    def load(self, conversation_id: str) -> dict[str, Any]:
        path = self.path_for(conversation_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"conversation file is not an object: {path}")
        data.setdefault("id", conversation_id)
        data.setdefault("title", "Untitled conversation")
        data.setdefault("created_at", utc_now())
        data.setdefault("updated_at", data["created_at"])
        data.setdefault("wire_format", "auto")
        messages = data.get("messages")
        data["messages"] = [normalize_message(m) for m in messages] if isinstance(messages, list) else []
        data["stats"] = conversation_stats(data["messages"])
        return data

    def save(self, conversation: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(conversation)
        cid = str(data.get("id") or _conversation_id())
        _clean_id(cid)
        stamp = utc_now()
        data["id"] = cid
        data.setdefault("created_at", stamp)
        data["updated_at"] = stamp
        messages = data.get("messages")
        data["messages"] = [normalize_message(m) for m in messages] if isinstance(messages, list) else []
        data["stats"] = conversation_stats(data["messages"])
        path = self.path_for(cid)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            tmp_name = handle.name
        Path(tmp_name).replace(path)
        return data

    def summary(self, conversation: Mapping[str, Any]) -> dict[str, Any]:
        messages = conversation.get("messages") if isinstance(conversation.get("messages"), list) else []
        return {
            "id": conversation.get("id"),
            "title": conversation.get("title"),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
            "model": conversation.get("model"),
            "wire_format": conversation.get("wire_format"),
            "stats": conversation_stats(messages),
        }

    def patch(self, conversation_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        data = self.load(conversation_id)
        for key in ("title", "model", "wire_format"):
            if key in updates:
                data[key] = updates[key]
        if "messages" in updates and isinstance(updates["messages"], list):
            data["messages"] = [normalize_message(m) for m in updates["messages"]]
        return self.save(data)

    def delete(self, conversation_id: str) -> bool:
        path = self.path_for(conversation_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def add_message(self, conversation_id: str, message: Mapping[str, Any]) -> dict[str, Any]:
        data = self.load(conversation_id)
        data.setdefault("messages", []).append(normalize_message(message))
        return self.save(data)

    def edit_message(self, conversation_id: str, message_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        data = self.load(conversation_id)
        stamp = utc_now()
        found = False
        for message in data["messages"]:
            if message.get("id") == message_id:
                if "role" in updates:
                    message["role"] = str(updates["role"])
                if "content" in updates:
                    message["content"] = updates["content"]
                message["updated_at"] = stamp
                found = True
                break
        if not found:
            raise KeyError(f"message not found: {message_id}")
        return self.save(data)

    def delete_message(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        data = self.load(conversation_id)
        before = len(data["messages"])
        data["messages"] = [m for m in data["messages"] if m.get("id") != message_id]
        if len(data["messages"]) == before:
            raise KeyError(f"message not found: {message_id}")
        return self.save(data)
