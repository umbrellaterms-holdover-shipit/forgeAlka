from __future__ import annotations

"""Flask API wrapper for the `apex` dev-machine toolkit.

The API deliberately exposes structured operations instead of arbitrary shell
execution. The CLI remains the source of truth for command grammar; this module
is the HTTP skin for the commands that make sense in a browser.
"""

from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4
import json
import os

from .documents.conversion import convert_file, render_available_conversions
from .llm.costs import estimate_request_costs
from .llm.model_catalog import load_models_snapshot, rows_from_snapshot, compact_model_options, write_starter_models
from .llm.preflight import PreflightContext, run_chat_preflight
from .config import secret_path, secret_status, write_secret
from .llm.openrouter import (
    OpenRouterClient,
    OpenRouterError,
    build_messages,
    payload_for_wire_format,
    run_nonstream_llm_request,
)
from .system_tools import dependency_report, install_system_tools
from .web.conversations import ConversationStore, infer_title

try:  # Flask is an optional dependency: install with `python -m pip install -e '.[web]'`.
    from flask import Flask, jsonify, request, send_from_directory
except Exception:  # pragma: no cover - exercised only when Flask is not installed.
    Flask = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]
    send_from_directory = None  # type: ignore[assignment]


DEFAULT_WORKDIR = Path(os.environ.get("APEX_WEB_WORKDIR", ".apex-web")).resolve()
DEFAULT_ALLOWED_TOOLS = {"ffmpeg", "pandoc"}


def _require_flask() -> None:
    if Flask is None:
        raise RuntimeError("Flask is not installed. Run: python -m pip install -e '.[web]'")


def _json_response(payload: Any, status: int = 200):
    assert jsonify is not None
    return jsonify(payload), status


def _error(message: str, status: int = 400, *, details: Any = None):
    body: dict[str, Any] = {"error": message}
    if details is not None:
        body["details"] = details
    return _json_response(body, status)


def _request_json() -> dict[str, Any]:
    assert request is not None
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return {}


def _parse_extra(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        if not isinstance(loaded, dict):
            raise ValueError("extra must decode to a JSON object")
        return loaded
    raise ValueError("extra must be an object or JSON object string")


def _messages_from_payload(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("messages"), list):
        messages = data["messages"]
        return [m for m in messages if isinstance(m, dict)]
    return build_messages(prompt=data.get("prompt"), system=data.get("system"))


def _dependency_status_to_dict(status: Any) -> dict[str, Any]:
    return {
        "name": status.name,
        "present": status.present,
        "path": str(status.path) if status.path else None,
        "version": status.version,
        "install_hint": status.install_hint,
    }


def _result_download_url(result_path: Path, workdir: Path) -> str | None:
    try:
        rel = result_path.resolve().relative_to(workdir.resolve())
    except ValueError:
        return None
    return f"/api/files/{rel.as_posix()}"


def create_app(config: Mapping[str, Any] | None = None):
    """Create the Flask app.

    Config keys:
      - WORKDIR: where uploads/results/rate snapshots are written.
      - ALLOW_INSTALL: allow /api/deps/install to run non-dry-run installs.
    """
    _require_flask()
    assert Flask is not None

    app = Flask(__name__)
    app.config.update(config or {})
    workdir = Path(app.config.get("WORKDIR") or DEFAULT_WORKDIR).resolve()
    uploads_dir = workdir / "uploads"
    results_dir = workdir / "results"
    rates_dir = workdir / "rates"
    conversations_dir = workdir / "conversations"
    for directory in (uploads_dir, results_dir, rates_dir, conversations_dir):
        directory.mkdir(parents=True, exist_ok=True)

    @app.after_request
    def add_dev_cors_headers(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization")
        response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        return response

    @app.route("/api/health", methods=["GET"])
    def health():
        return _json_response({"ok": True, "app": "apex", "workdir": str(workdir)})

    @app.route("/api/commands", methods=["GET"])
    def commands():
        return _json_response(
            {
                "cli": "apex",
                "endpoints": {
                    "llm": "POST /api/llm",
                    "chat": "POST /api/chat",
                    "convert": "POST /api/convert",
                    "deps_doctor": "POST /api/deps/doctor",
                    "deps_install": "POST /api/deps/install",
                    "models_refresh": "POST /api/models/refresh",
                    "models_list": "POST /api/models/list",
                    "models_seed": "POST /api/models/seed",
                    "cost": "POST /api/cost",
                    "chat_preflight": "POST /api/chat/preflight",
                    "conversations": "GET/POST /api/conversations",
                    "conversation": "GET/PATCH/DELETE /api/conversations/<id>",
                    "conversation_messages": "POST/PATCH/DELETE /api/conversations/<id>/messages",
                    "keys_status": "GET/POST /api/keys/status",
                    "keys_set": "POST /api/keys/set",
                },
                "wire_formats": ["auto", "openai-responses", "anthropic-messages", "chat-completions"],
                "conversions": render_available_conversions(),
            }
        )


    store = ConversationStore(conversations_dir)

    @app.route("/api/conversations", methods=["GET", "POST", "OPTIONS"])
    def conversations():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        if request.method == "GET":
            return _json_response({"conversations": store.list()})
        data = _request_json()
        try:
            conversation = store.create(
                title=data.get("title"),
                model=data.get("model"),
                wire_format=data.get("wire_format"),
                messages=data.get("messages") if isinstance(data.get("messages"), list) else None,
            )
            return _json_response(conversation, 201)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/conversations/<conversation_id>", methods=["GET", "PATCH", "DELETE", "OPTIONS"])
    def conversation_detail(conversation_id: str):
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        try:
            if request.method == "GET":
                return _json_response(store.load(conversation_id))
            if request.method == "DELETE":
                return _json_response({"deleted": store.delete(conversation_id), "id": conversation_id})
            return _json_response(store.patch(conversation_id, _request_json()))
        except FileNotFoundError:
            return _error(f"conversation not found: {conversation_id}", 404)
        except KeyError as exc:
            return _error(str(exc), 404)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/conversations/<conversation_id>/messages", methods=["POST", "OPTIONS"])
    def conversation_messages(conversation_id: str):
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        try:
            data = _request_json()
            return _json_response(store.add_message(conversation_id, data))
        except FileNotFoundError:
            return _error(f"conversation not found: {conversation_id}", 404)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/conversations/<conversation_id>/messages/<message_id>", methods=["PATCH", "DELETE", "OPTIONS"])
    def conversation_message_detail(conversation_id: str, message_id: str):
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        try:
            if request.method == "DELETE":
                return _json_response(store.delete_message(conversation_id, message_id))
            return _json_response(store.edit_message(conversation_id, message_id, _request_json()))
        except FileNotFoundError:
            return _error(f"conversation not found: {conversation_id}", 404)
        except KeyError as exc:
            return _error(str(exc), 404)
        except Exception as exc:
            return _error(str(exc), 400)


    @app.route("/api/keys/status", methods=["GET", "POST", "OPTIONS"])
    def keys_status():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        provider = str(data.get("provider") or request.args.get("provider") or "openrouter")
        path = data.get("path") or request.args.get("path")
        return _json_response(secret_status(provider, path).to_dict())

    @app.route("/api/keys/set", methods=["POST", "OPTIONS"])
    def keys_set():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        provider = str(data.get("provider") or "openrouter")
        value = str(data.get("api_key") or data.get("value") or "").strip()
        if not value:
            return _error("api_key is required")
        try:
            path = write_secret(value, provider, data.get("path"))
            return _json_response({"provider": provider, "path": str(path), "status": secret_status(provider, path).to_dict()})
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/llm", methods=["POST", "OPTIONS"])
    def llm():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        try:
            model = str(data.get("model") or "").strip()
            if not model:
                return _error("model is required")
            messages = _messages_from_payload(data)
            wire_format = str(data.get("wire_format") or "auto")
            temperature = data.get("temperature")
            max_tokens = data.get("max_tokens")
            extra = _parse_extra(data.get("extra"))
            resolved, endpoint, payload = payload_for_wire_format(
                model=model,
                messages=messages,
                wire_format=wire_format,
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                extra=extra,
            )
            if data.get("dry_run"):
                return _json_response({"wire_format": resolved, "endpoint": endpoint, "payload": payload})
            client = OpenRouterClient(
                api_key=data.get("api_key"),
                api_key_file=data.get("api_key_file"),
                base_url=data.get("base_url") or "https://openrouter.ai/api/v1",
                http_referer=data.get("http_referer"),
                title=data.get("title") or "apex-dev-web",
                timeout_s=float(data.get("timeout") or 120.0),
            )
            result = run_nonstream_llm_request(
                client=client,
                model=model,
                messages=messages,
                wire_format=wire_format,
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                extra=extra,
            )
            return _json_response(result)
        except OpenRouterError as exc:
            return _error(str(exc), exc.status or 502, details=exc.payload)
        except Exception as exc:
            return _error(str(exc), 400)


    @app.route("/api/chat/preflight", methods=["POST", "OPTIONS"])
    def chat_preflight():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        try:
            messages = _messages_from_payload(data)
            if "prompt" in data and not isinstance(data.get("messages"), list):
                history = messages
            else:
                history = [m for m in messages if isinstance(m, dict)]
            model = str(data.get("model") or "").strip()
            if not model:
                return _error("model is required")
            rates_path = Path(data.get("rates_path") or (rates_dir / "openrouter.models.json"))
            max_tokens = data.get("max_tokens")
            ctx = PreflightContext(
                model=model,
                messages=history,
                rates_path=rates_path,
                max_tokens=int(max_tokens) if max_tokens not in (None, "") else None,
                wire_format=str(data.get("wire_format") or "auto"),
            )
            result = run_chat_preflight(ctx)
            resolved, endpoint, payload = payload_for_wire_format(
                model=model,
                messages=history,
                wire_format=ctx.wire_format,
                temperature=float(data["temperature"]) if data.get("temperature") not in (None, "") else None,
                max_tokens=ctx.max_tokens,
                extra=_parse_extra(data.get("extra")),
            )
            return _json_response({**result, "wire_format": resolved, "endpoint": endpoint, "payload": payload})
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/chat", methods=["POST", "OPTIONS"])
    def chat():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        try:
            messages = _messages_from_payload(data)
            if "prompt" in data and not isinstance(data.get("messages"), list):
                history = messages
            else:
                history = [m for m in messages if isinstance(m, dict)]
            data = dict(data)
            data["messages"] = history
            data.pop("prompt", None)
            model = str(data.get("model") or "").strip()
            if not model:
                return _error("model is required")
            wire_format = str(data.get("wire_format") or "auto")
            temperature = data.get("temperature")
            max_tokens = data.get("max_tokens")
            extra = _parse_extra(data.get("extra"))
            resolved, endpoint, payload = payload_for_wire_format(
                model=model,
                messages=history,
                wire_format=wire_format,
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                extra=extra,
            )
            if data.get("dry_run"):
                return _json_response({"wire_format": resolved, "endpoint": endpoint, "payload": payload, "messages": history})
            client = OpenRouterClient(
                api_key=data.get("api_key"),
                api_key_file=data.get("api_key_file"),
                base_url=data.get("base_url") or "https://openrouter.ai/api/v1",
                http_referer=data.get("http_referer"),
                title=data.get("title") or "apex-dev-web",
                timeout_s=float(data.get("timeout") or 120.0),
            )
            result = run_nonstream_llm_request(
                client=client,
                model=model,
                messages=history,
                wire_format=wire_format,
                temperature=float(temperature) if temperature is not None else None,
                max_tokens=int(max_tokens) if max_tokens is not None else None,
                extra=extra,
            )
            assistant_message = {"role": "assistant", "content": result["text"]}
            saved_messages = [*history, assistant_message]
            conversation = None
            conversation_id = data.get("conversation_id")
            if conversation_id:
                if store.exists(str(conversation_id)):
                    conversation = store.patch(
                        str(conversation_id),
                        {
                            "messages": saved_messages,
                            "model": model,
                            "wire_format": wire_format,
                            **({"title": data.get("title")} if data.get("title") else {}),
                        },
                    )
                else:
                    conversation = store.create(
                        conversation_id=str(conversation_id),
                        title=data.get("title") or infer_title(saved_messages),
                        model=model,
                        wire_format=wire_format,
                        messages=saved_messages,
                    )
            elif data.get("save", True):
                conversation = store.create(
                    title=data.get("title") or infer_title(saved_messages),
                    model=model,
                    wire_format=wire_format,
                    messages=saved_messages,
                )
            body = {**result, "assistant_message": assistant_message, "messages": saved_messages}
            if conversation is not None:
                body["conversation"] = conversation
                body["conversation_id"] = conversation["id"]
            return _json_response(body)
        except OpenRouterError as exc:
            return _error(str(exc), exc.status or 502, details=exc.payload)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/convert", methods=["POST", "OPTIONS"])
    def convert():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        try:
            if request.files:
                upload = request.files.get("file")
                if upload is None or not upload.filename:
                    return _error("file upload is required")
                source_name = Path(upload.filename).name
                stem = Path(source_name).stem or "upload"
                suffix = Path(source_name).suffix or ""
                upload_path = uploads_dir / f"{uuid4().hex}_{stem}{suffix}"
                upload.save(upload_path)
                to_format = request.form.get("to_format") or request.form.get("to")
                from_format = request.form.get("from_format") or request.form.get("from")
                if not to_format:
                    return _error("to_format is required for uploaded conversions")
                out_path = results_dir / f"{uuid4().hex}_{stem}.{to_format.lstrip('.')}"
                prefer_pandoc = request.form.get("no_pandoc") not in {"1", "true", "yes"}
            else:
                data = _request_json()
                input_path = data.get("input")
                output_path = data.get("output")
                if not input_path or not output_path:
                    return _error("input and output are required for JSON conversion requests")
                upload_path = Path(input_path)
                out_path = Path(output_path)
                from_format = data.get("from_format") or data.get("from")
                to_format = data.get("to_format") or data.get("to")
                prefer_pandoc = not bool(data.get("no_pandoc"))
            result = convert_file(upload_path, out_path, from_format=from_format, to_format=to_format, prefer_pandoc=prefer_pandoc)
            body = result.to_dict()
            download_url = _result_download_url(Path(result.output_path), workdir)
            if download_url:
                body["download_url"] = download_url
            return _json_response(body)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/files/<path:filename>", methods=["GET"])
    def files(filename: str):
        assert send_from_directory is not None
        return send_from_directory(workdir, filename, as_attachment=True)

    @app.route("/api/deps/doctor", methods=["POST", "GET", "OPTIONS"])
    def deps_doctor():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        tools = data.get("tools") if isinstance(data.get("tools"), list) else ["ffmpeg", "pandoc"]
        return _json_response({"tools": [_dependency_status_to_dict(s) for s in dependency_report(tools)]})

    @app.route("/api/deps/install", methods=["POST", "OPTIONS"])
    def deps_install():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        tools = data.get("tools") if isinstance(data.get("tools"), list) else ["ffmpeg", "pandoc"]
        tools = [str(t) for t in tools]
        illegal = sorted(set(tools) - DEFAULT_ALLOWED_TOOLS)
        if illegal:
            return _error(f"unsupported install target(s): {', '.join(illegal)}")
        dry_run = bool(data.get("dry_run", True))
        if not dry_run and not app.config.get("ALLOW_INSTALL", False):
            return _error("non-dry-run installs are disabled unless the Flask app is created with ALLOW_INSTALL=True", 403)
        log = install_system_tools(tools, assume_yes=bool(data.get("yes", True)), dry_run=dry_run, only_missing=not bool(data.get("force")))
        return _json_response({"dry_run": dry_run, "log": log})

    @app.route("/api/models/refresh", methods=["POST", "OPTIONS"])
    def models_refresh():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        try:
            out = Path(data.get("out") or (rates_dir / "openrouter.models.json"))
            client = OpenRouterClient(
                api_key=data.get("api_key"),
                api_key_file=data.get("api_key_file"),
                base_url=data.get("base_url") or "https://openrouter.ai/api/v1",
                http_referer=data.get("http_referer"),
                title=data.get("title") or "apex-dev-web",
                timeout_s=float(data.get("timeout") or 120.0),
            )
            path = client.write_models_snapshot(out, require_auth=bool(data.get("require_auth")))
            return _json_response({"path": str(path)})
        except OpenRouterError as exc:
            return _error(str(exc), exc.status or 502, details=exc.payload)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/models/list", methods=["POST", "GET", "OPTIONS"])
    def models_list():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        path = Path(data.get("input") or (rates_dir / "openrouter.models.json"))
        limit = int(data.get("limit") or 100)
        fallback = not bool(data.get("no_seed_fallback"))
        try:
            snapshot, source = load_models_snapshot(path, fallback_to_seed=fallback)
            rows = compact_model_options(rows_from_snapshot(snapshot), limit=limit)
            return _json_response({"models": rows, "source": source, "seed_fallback": source == "bundled-starter-catalog"})
        except FileNotFoundError:
            return _error(f"model snapshot not found: {path}", 404)
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/models/seed", methods=["POST", "OPTIONS"])
    def models_seed():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        data = _request_json()
        out = Path(data.get("out") or (rates_dir / "openrouter.models.json"))
        try:
            path = write_starter_models(out)
            return _json_response({"path": str(path)})
        except Exception as exc:
            return _error(str(exc), 400)

    @app.route("/api/cost", methods=["POST", "OPTIONS"])
    def cost():
        if request.method == "OPTIONS":
            return _json_response({"ok": True})
        try:
            if request.files:
                rates_upload = request.files.get("rates")
                requests_upload = request.files.get("requests")
                if rates_upload is None or requests_upload is None:
                    return _error("multipart cost requests need rates and requests files")
                rates_path = uploads_dir / f"{uuid4().hex}_{Path(rates_upload.filename or 'rates.json').name}"
                requests_path = uploads_dir / f"{uuid4().hex}_{Path(requests_upload.filename or 'requests.jsonl').name}"
                rates_upload.save(rates_path)
                requests_upload.save(requests_path)
            else:
                data = _request_json()
                rates_path = Path(data.get("rates") or "")
                requests_path = Path(data.get("requests") or "")
                if not rates_path or not requests_path:
                    return _error("rates and requests paths are required")
            return _json_response(estimate_request_costs(rates_path, requests_path))
        except Exception as exc:
            return _error(str(exc), 400)

    return app


def run_dev_server(*, host: str = "127.0.0.1", port: int = 8765, debug: bool = False, workdir: str | Path | None = None, allow_install: bool = False) -> None:
    """Run the Flask dev server for local/Codespaces use."""
    app = create_app({"WORKDIR": str(workdir or DEFAULT_WORKDIR), "ALLOW_INSTALL": allow_install})
    app.run(host=host, port=port, debug=debug)
