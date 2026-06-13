from __future__ import annotations

"""Small OpenRouter client built on the Python standard library.

The client deliberately avoids a hard dependency on the OpenAI SDK. OpenRouter
is OpenAI-compatible for chat-completions calls, but a tiny HTTP wrapper is
simpler to vendor into a Codespaces bootstrap project and easier to test.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping
from urllib import error, parse, request
import json
import time

from apexdev.config import resolve_api_key, secret_path

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_APP_TITLE = "apex-dev"


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter returns an HTTP/API error."""

    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    http_referer: str | None = None
    title: str = DEFAULT_APP_TITLE
    timeout_s: float = 120.0


def default_api_key_file() -> Path:
    """Return the default file-backed OpenRouter key path."""
    return secret_path("openrouter")


def load_messages(path: str | Path) -> list[dict[str, Any]]:
    """Load chat messages from JSON or JSONL.

    JSON may be either a list of `{role, content}` messages or an object with a
    `messages` list. JSONL should contain one message per line.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    raise ValueError(f"{p} must contain a message list or an object with a 'messages' list")


def build_messages(*, prompt: str | None = None, system: str | None = None, messages_file: str | Path | None = None) -> list[dict[str, Any]]:
    """Build a chat-completions message list from CLI-style inputs."""
    messages: list[dict[str, Any]] = []
    if messages_file:
        messages.extend(load_messages(messages_file))
    if system:
        messages.insert(0, {"role": "system", "content": system})
    if prompt:
        messages.append({"role": "user", "content": prompt})
    if not messages:
        raise ValueError("Provide --prompt, --messages, or both")
    return messages




def _content_text(content: Any) -> str:
    """Best-effort plain-text extraction from chat/message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
        return "".join(parts)
    return ""


def split_instructions(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """Pull system/developer messages into Responses `instructions` text.

    The Responses API accepts a top-level `instructions` field for system-like
    guidance. Chat Completions-style message files often contain `system` or
    `developer` entries, so this lets the same JSON/JSONL file feed either API.
    """
    instructions: list[str] = []
    kept: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        if role in {"system", "developer"}:
            text = _content_text(message.get("content"))
            if text:
                instructions.append(text)
        else:
            kept.append(message)
    return ("\n\n".join(instructions) if instructions else None), kept


def messages_to_responses_input(messages: list[dict[str, Any]]) -> tuple[str | list[dict[str, Any]], str | None]:
    """Convert Chat Completions-style messages to Responses API input.

    For a single user message this returns a simple string input. For real
    conversations it emits OpenAI/OpenRouter Responses-style message objects.
    Assistant history gets a synthetic id/status when needed because OpenRouter
    documents those fields as required for assistant messages in conversation
    history.
    """
    instructions, kept = split_instructions(messages)
    if len(kept) == 1 and kept[0].get("role") == "user":
        return _content_text(kept[0].get("content")), instructions
    items: list[dict[str, Any]] = []
    for i, message in enumerate(kept):
        role = str(message.get("role", "user"))
        text = _content_text(message.get("content"))
        part_type = "output_text" if role == "assistant" else "input_text"
        item: dict[str, Any] = {
            "type": "message",
            "role": role,
            "content": [{"type": part_type, "text": text}],
        }
        if role == "assistant":
            item["id"] = str(message.get("id") or f"msg_local_{i}")
            item["status"] = str(message.get("status") or "completed")
        items.append(item)
    return items, instructions

def _json_loads_maybe(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}



WIRE_FORMATS = {"auto", "openai-responses", "anthropic-messages", "chat-completions"}


def resolve_wire_format(model: str, wire_format: str = "auto") -> str:
    """Resolve `auto` to the provider-shaped OpenRouter wire format."""
    if wire_format not in WIRE_FORMATS:
        raise ValueError(f"unknown OpenRouter wire format: {wire_format}")
    return recommended_wire_format_for_model(model) if wire_format == "auto" else wire_format


def endpoint_for_wire_format(wire_format: str) -> str:
    """Return the OpenRouter endpoint path for a resolved wire format."""
    if wire_format == "openai-responses":
        return "/responses"
    if wire_format == "anthropic-messages":
        return "/messages"
    if wire_format == "chat-completions":
        return "/chat/completions"
    raise ValueError(f"unknown OpenRouter wire format: {wire_format}")


def payload_for_wire_format(
    *,
    model: str,
    messages: list[dict[str, Any]],
    wire_format: str = "auto",
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Build the endpoint-specific OpenRouter payload without sending it.

    Returns `(resolved_wire_format, endpoint, payload)`. This is the shared
    seam used by the CLI, Flask API, and React dry-run view so API compatibility
    sludge stays in one place instead of reproducing like mold.
    """
    resolved = resolve_wire_format(model, wire_format)
    payload: dict[str, Any]
    if resolved == "openai-responses":
        input_payload, instructions = messages_to_responses_input(messages)
        payload = {"model": model, "input": input_payload}
        if instructions:
            payload["instructions"] = instructions
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
    elif resolved == "anthropic-messages":
        instructions, kept = split_instructions(messages)
        payload = {"model": model, "messages": kept}
        if instructions:
            payload["system"] = instructions
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
    elif resolved == "chat-completions":
        payload = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
    else:  # pragma: no cover - resolve_wire_format rejects this first.
        raise ValueError(f"unknown OpenRouter wire format: {resolved}")
    if extra:
        payload.update(dict(extra))
    return resolved, endpoint_for_wire_format(resolved), payload


def text_from_wire_response(response: Mapping[str, Any], wire_format: str) -> str:
    """Extract assistant text according to the resolved wire format."""
    if wire_format == "openai-responses":
        return text_from_response_api(response)
    if wire_format == "anthropic-messages":
        return text_from_message_api(response)
    if wire_format == "chat-completions":
        return chat_text_from_response(response)
    raise ValueError(f"unknown OpenRouter wire format: {wire_format}")


def run_nonstream_llm_request(
    *,
    client: "OpenRouterClient",
    model: str,
    messages: list[dict[str, Any]],
    wire_format: str = "auto",
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Send one non-streaming OpenRouter request and return normalized metadata."""
    resolved, endpoint, payload = payload_for_wire_format(
        model=model,
        messages=messages,
        wire_format=wire_format,
        temperature=temperature,
        max_tokens=max_tokens,
        extra=extra,
    )
    if resolved == "openai-responses":
        response = client.create_response(
            model=model,
            input=payload["input"],
            instructions=payload.get("instructions"),
            temperature=payload.get("temperature"),
            max_output_tokens=payload.get("max_output_tokens"),
            extra={k: v for k, v in payload.items() if k not in {"model", "input", "instructions", "temperature", "max_output_tokens"}},
        )
    elif resolved == "anthropic-messages":
        response = client.create_message(
            model=model,
            messages=payload["messages"],
            system=payload.get("system"),
            temperature=payload.get("temperature"),
            max_tokens=payload.get("max_tokens"),
            extra={k: v for k, v in payload.items() if k not in {"model", "messages", "system", "temperature", "max_tokens"}},
        )
    else:
        response = client.chat_completion(
            model=model,
            messages=payload["messages"],
            temperature=payload.get("temperature"),
            max_tokens=payload.get("max_tokens"),
            extra={k: v for k, v in payload.items() if k not in {"model", "messages", "temperature", "max_tokens"}},
        )
    assert isinstance(response, Mapping)
    return {
        "wire_format": resolved,
        "endpoint": endpoint,
        "payload": payload,
        "text": text_from_wire_response(response, resolved),
        "raw": response,
    }

class OpenRouterClient:
    """Minimal OpenRouter HTTP client."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_key_file: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_referer: str | None = None,
        title: str = DEFAULT_APP_TITLE,
        timeout_s: float = 120.0,
    ) -> None:
        self.config = OpenRouterConfig(
            api_key=resolve_api_key(explicit_key=api_key, provider="openrouter", path=api_key_file),
            base_url=base_url.rstrip("/"),
            http_referer=http_referer,
            title=title,
            timeout_s=timeout_s,
        )

    def _headers(self, *, require_auth: bool = True) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"{self.config.title}/0.8",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif require_auth:
            raise OpenRouterError(f"OpenRouter API key not found. Run `apex keys set openrouter --stdin` or write {default_api_key_file()}.")
        if self.config.http_referer:
            headers["HTTP-Referer"] = self.config.http_referer
        if self.config.title:
            headers["X-Title"] = self.config.title
        return headers

    def _url(self, path: str, params: Mapping[str, str] | None = None) -> str:
        path = path if path.startswith("/") else f"/{path}"
        url = f"{self.config.base_url}{path}"
        if params:
            url += "?" + parse.urlencode(params)
        return url

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, str] | None = None,
        require_auth: bool = True,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(
            self._url(path, params),
            data=data,
            method=method.upper(),
            headers=self._headers(require_auth=require_auth),
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_s) as resp:
                raw = resp.read()
        except error.HTTPError as exc:
            payload = _json_loads_maybe(exc.read())
            message = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise OpenRouterError(message or f"OpenRouter HTTP {exc.code}", status=exc.code, payload=payload) from exc
        except error.URLError as exc:
            raise OpenRouterError(f"OpenRouter request failed: {exc.reason}") from exc
        return _json_loads_maybe(raw)

    def list_models(self, *, require_auth: bool = False) -> dict[str, Any]:
        """Return `/models` response data."""
        return self._request_json("GET", "/models", require_auth=require_auth)

    def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | Iterator[dict[str, Any]]:
        """Create a chat completion.

        Non-streaming returns the decoded JSON response. Streaming yields parsed
        server-sent-event JSON chunks and ignores `[DONE]` markers.
        """
        body: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if extra:
            body.update(dict(extra))
        if stream:
            body["stream"] = True
            return self._stream_chat(body)
        return self._request_json("POST", "/chat/completions", body=body, require_auth=True)


    def create_response(
        self,
        *,
        model: str,
        input: str | list[dict[str, Any]],
        instructions: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        stream: bool = False,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | Iterator[dict[str, Any]]:
        """Create a response via OpenRouter's OpenAI-compatible Responses API."""
        body: dict[str, Any] = {"model": model, "input": input}
        if instructions:
            body["instructions"] = instructions
        if temperature is not None:
            body["temperature"] = temperature
        if max_output_tokens is not None:
            body["max_output_tokens"] = max_output_tokens
        if extra:
            body.update(dict(extra))
        if stream:
            body["stream"] = True
            return self._stream_endpoint("/responses", body)
        return self._request_json("POST", "/responses", body=body, require_auth=True)

    def create_message(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | Iterator[dict[str, Any]]:
        """Create a message via OpenRouter's Anthropic-compatible Messages API."""
        instructions, kept = split_instructions(messages)
        body: dict[str, Any] = {"model": model, "messages": kept}
        system_text = system or instructions
        if system_text:
            body["system"] = system_text
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if extra:
            body.update(dict(extra))
        if stream:
            body["stream"] = True
            return self._stream_endpoint("/messages", body)
        return self._request_json("POST", "/messages", body=body, require_auth=True)

    def _stream_endpoint(self, path: str, body: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        req = request.Request(
            self._url(path),
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=self._headers(require_auth=True),
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_s) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    yield json.loads(payload)
        except error.HTTPError as exc:
            payload = _json_loads_maybe(exc.read())
            raise OpenRouterError(f"OpenRouter HTTP {exc.code}", status=exc.code, payload=payload) from exc
        except error.URLError as exc:
            raise OpenRouterError(f"OpenRouter stream failed: {exc.reason}") from exc

    def _stream_chat(self, body: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        req = request.Request(
            self._url("/chat/completions"),
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers=self._headers(require_auth=True),
        )
        try:
            with request.urlopen(req, timeout=self.config.timeout_s) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    yield json.loads(payload)
        except error.HTTPError as exc:
            payload = _json_loads_maybe(exc.read())
            raise OpenRouterError(f"OpenRouter HTTP {exc.code}", status=exc.code, payload=payload) from exc
        except error.URLError as exc:
            raise OpenRouterError(f"OpenRouter stream failed: {exc.reason}") from exc

    def generation(self, generation_id: str) -> dict[str, Any]:
        return self._request_json("GET", "/generation", params={"id": generation_id}, require_auth=True)

    def write_models_snapshot(self, path: str | Path, *, require_auth: bool = False) -> Path:
        data = self.list_models(require_auth=require_auth)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "source": "openrouter:/api/v1/models",
            "created_at_unix": time.time(),
            "data": data.get("data", data),
        }
        out.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
        return out


def chat_text_from_response(response: Mapping[str, Any]) -> str:
    """Extract assistant text from an OpenAI/OpenRouter chat-completion response."""
    choices = response.get("choices")
    if not choices:
        return ""
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
    delta = first.get("delta") if isinstance(first, dict) else None
    if isinstance(delta, dict) and isinstance(delta.get("content"), str):
        return delta["content"]
    return ""




def text_from_response_api(response: Mapping[str, Any]) -> str:
    """Extract text from OpenAI/OpenRouter Responses API output."""
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text
    parts: list[str] = []
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
    return "".join(parts)


def text_from_message_api(response: Mapping[str, Any]) -> str:
    """Extract text from Anthropic Messages-style output."""
    content = response.get("content")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, Mapping):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
    return "".join(parts)


def response_stream_delta_text(chunk: Mapping[str, Any]) -> str:
    if chunk.get("type") == "response.content_part.delta" and isinstance(chunk.get("delta"), str):
        return chunk["delta"]
    delta = chunk.get("delta")
    if isinstance(delta, str):
        return delta
    return ""


def message_stream_delta_text(chunk: Mapping[str, Any]) -> str:
    if chunk.get("type") == "content_block_delta":
        delta = chunk.get("delta")
        if isinstance(delta, Mapping) and isinstance(delta.get("text"), str):
            return delta["text"]
    delta = chunk.get("delta")
    if isinstance(delta, Mapping) and isinstance(delta.get("text"), str):
        return delta["text"]
    return ""


def recommended_wire_format_for_model(model: str) -> str:
    """Return the least-surprising OpenRouter compatibility wire format for a model slug."""
    normalized = model.lstrip("~").lower()
    if normalized.startswith("openai/"):
        return "openai-responses"
    if normalized.startswith("anthropic/"):
        return "anthropic-messages"
    return "chat-completions"


def recommended_api_for_model(model: str) -> str:
    """Backward-compatible alias for older callers. Prefer recommended_wire_format_for_model."""
    return recommended_wire_format_for_model(model)

def stream_delta_text(chunk: Mapping[str, Any]) -> str:
    choices = chunk.get("choices")
    if not choices:
        return ""
    first = choices[0]
    delta = first.get("delta") if isinstance(first, dict) else None
    if isinstance(delta, dict):
        content = delta.get("content")
        return content if isinstance(content, str) else ""
    return ""
