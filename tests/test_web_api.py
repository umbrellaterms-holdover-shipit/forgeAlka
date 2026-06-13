import json

import pytest

from apexdev.cli import main
from apexdev.llm.openrouter import build_messages, payload_for_wire_format, resolve_wire_format


def test_wire_format_payload_builder_for_web_api():
    messages = build_messages(prompt="hello", system="be terse")
    wire, endpoint, payload = payload_for_wire_format(model="openai/gpt-5", messages=messages)
    assert wire == "openai-responses"
    assert endpoint == "/responses"
    assert payload["input"] == "hello"
    assert payload["instructions"] == "be terse"

    wire, endpoint, payload = payload_for_wire_format(model="anthropic/claude-sonnet-4", messages=messages)
    assert wire == "anthropic-messages"
    assert endpoint == "/messages"
    assert payload["system"] == "be terse"
    assert payload["messages"][0]["role"] == "user"

    assert resolve_wire_format("example/model", "chat-completions") == "chat-completions"


def test_web_info_cli(capsys):
    main(["web", "info"])
    data = json.loads(capsys.readouterr().out)
    assert data["api"].startswith("apex web api")
    assert "apps/web" in data["react_dev"]


def test_flask_api_dry_run_if_installed(tmp_path):
    pytest.importorskip("flask")
    from apexdev.web_api import create_app

    app = create_app({"WORKDIR": str(tmp_path)})
    client = app.test_client()
    health = client.get("/api/health")
    assert health.status_code == 200
    response = client.post(
        "/api/chat",
        json={"model": "openai/gpt-5", "prompt": "hello", "dry_run": True},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["wire_format"] == "openai-responses"
    assert data["endpoint"] == "/responses"


def test_flask_keys_and_preflight_if_installed(tmp_path):
    pytest.importorskip("flask")
    from apexdev.web_api import create_app

    rates_dir = tmp_path / "rates"
    rates_dir.mkdir()
    (rates_dir / "openrouter.models.json").write_text(
        json.dumps({"data": [{"id": "example/model", "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"}}]}),
        encoding="utf-8",
    )
    app = create_app({"WORKDIR": str(tmp_path)})
    client = app.test_client()
    key_path = tmp_path / "keys" / "openrouter.key"
    response = client.post("/api/keys/set", json={"provider": "openrouter", "path": str(key_path), "api_key": "sk-web-test"})
    assert response.status_code == 200
    assert response.get_json()["status"]["exists"] is True
    response = client.post(
        "/api/chat/preflight",
        json={"model": "example/model", "prompt": "hello", "max_tokens": 5},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["requires_confirmation"] is True
    assert data["checks"][0]["id"] == "cost-confirmation"


def test_conversation_store_stats_edit_delete(tmp_path):
    from apexdev.web.conversations import ConversationStore

    store = ConversationStore(tmp_path / "conversations")
    conv = store.create(title="Test", model="example/model", messages=[{"role": "user", "content": "hello there"}])
    assert conv["stats"]["messages"] == 1
    msg_id = conv["messages"][0]["id"]
    conv = store.edit_message(conv["id"], msg_id, {"content": "edited hello"})
    assert conv["messages"][0]["content"] == "edited hello"
    conv = store.add_message(conv["id"], {"role": "assistant", "content": "hi"})
    assert conv["stats"]["turns"] == 1
    conv = store.delete_message(conv["id"], msg_id)
    assert conv["stats"]["user_messages"] == 0


def test_flask_conversation_endpoints_if_installed(tmp_path):
    pytest.importorskip("flask")
    from apexdev.web_api import create_app

    app = create_app({"WORKDIR": str(tmp_path)})
    client = app.test_client()
    created = client.post("/api/conversations", json={"title": "Saved", "messages": [{"role": "user", "content": "hello"}]})
    assert created.status_code == 201
    conv = created.get_json()
    msg_id = conv["messages"][0]["id"]
    assert (tmp_path / "conversations" / f"{conv['id']}.json").exists()
    patched = client.patch(f"/api/conversations/{conv['id']}/messages/{msg_id}", json={"content": "updated"})
    assert patched.status_code == 200
    assert patched.get_json()["messages"][0]["content"] == "updated"
    listed = client.get("/api/conversations")
    assert listed.status_code == 200
    assert listed.get_json()["conversations"][0]["stats"]["estimated_tokens"] > 0
