import json
from pathlib import Path

from apexdev.cli import main
from apexdev.llm.costs import estimate_request_costs, load_rate_card
from apexdev.llm.openrouter import build_messages, chat_text_from_response, messages_to_responses_input, text_from_response_api, text_from_message_api, recommended_wire_format_for_model


def test_build_messages_and_response_text(tmp_path):
    messages = build_messages(prompt="Hello", system="You are terse.")
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "Hello"
    assert chat_text_from_response({"choices": [{"message": {"content": "hi"}}]}) == "hi"

    msg_file = tmp_path / "messages.json"
    msg_file.write_text(json.dumps({"messages": [{"role": "user", "content": "From file"}]}), encoding="utf-8")
    assert build_messages(messages_file=msg_file)[0]["content"] == "From file"


def test_responses_and_messages_helpers():
    messages = build_messages(prompt="Hello", system="You are terse.")
    input_payload, instructions = messages_to_responses_input(messages)
    assert input_payload == "Hello"
    assert instructions == "You are terse."
    assert text_from_response_api({"output": [{"content": [{"type": "output_text", "text": "hi"}]}]}) == "hi"
    assert text_from_message_api({"content": [{"type": "text", "text": "claude-ish"}]}) == "claude-ish"
    assert recommended_wire_format_for_model("openai/gpt-5") == "openai-responses"
    assert recommended_wire_format_for_model("anthropic/claude-sonnet-4") == "anthropic-messages"
    assert recommended_wire_format_for_model("mistralai/model") == "chat-completions"


def test_cost_estimator_openrouter_shape(tmp_path):
    rates = tmp_path / "rates.json"
    rates.write_text(
        json.dumps(
            {
                "source": "fixture",
                "data": [
                    {
                        "id": "provider/model",
                        "pricing": {
                            "prompt": "0.000000001",
                            "completion": "0.000000002",
                            "request": "0.001",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    requests = tmp_path / "requests.jsonl"
    requests.write_text('{"model":"provider/model","usage":{"prompt_tokens":1000,"completion_tokens":500}}\n', encoding="utf-8")
    report = estimate_request_costs(rates, requests)
    assert report["request_count"] == 1
    assert report["by_model"]["provider/model"]["prompt_tokens"] == 1000
    assert report["total_usd"] == "0.00100200"


def test_cost_cli_and_dry_run_llm(tmp_path, capsys):
    rates = tmp_path / "rates.json"
    requests = tmp_path / "requests.json"
    main(["rates", "example", "--out", str(rates)])
    data = json.loads(rates.read_text())
    assert data["data"][0]["id"] == "example/model"
    requests.write_text(json.dumps({"model": "example/model", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}), encoding="utf-8")
    main(["cost", "--rates", str(rates), "--requests", str(requests), "--json"])
    assert "total_usd" in capsys.readouterr().out

    main(["llm", "--model", "example/model", "--prompt", "hello", "--dry-run", "--wire-format", "chat-completions"])
    out = capsys.readouterr().out
    assert "example/model" in out and "messages" in out

    main(["llm", "--model", "openai/gpt-5", "--prompt", "hello", "--dry-run"])
    out = capsys.readouterr().out
    assert '"wire_format": "openai-responses"' in out and '"endpoint": "/responses"' in out

    main(["llm", "--model", "openai/gpt-5", "--prompt", "hello", "--dry-run", "--wire-format", "openai-responses"])
    out = capsys.readouterr().out
    assert '"input": "hello"' in out

    main(["llm", "--model", "anthropic/claude-sonnet-4", "--prompt", "hello", "--dry-run", "--wire-format", "anthropic-messages"])
    out = capsys.readouterr().out
    assert '"messages"' in out and "anthropic/claude" in out


def test_file_backed_openrouter_key_and_cli(tmp_path, capsys):
    from apexdev.config import read_secret, secret_status
    key_path = tmp_path / "openrouter.key"
    main(["keys", "set", "openrouter", "--path", str(key_path), "--value", "sk-test-file-key"])
    capsys.readouterr()
    assert read_secret("openrouter", key_path) == "sk-test-file-key"
    assert secret_status("openrouter", key_path).exists is True
    main(["keys", "status", "openrouter", "--path", str(key_path), "--json"])
    status = json.loads(capsys.readouterr().out)
    assert status["exists"] is True
    assert status["path"] == str(key_path)


def test_chat_preflight_cost_confirmation(tmp_path):
    from apexdev.llm.preflight import PreflightContext, run_chat_preflight
    rates = tmp_path / "rates.json"
    rates.write_text(
        json.dumps({"data": [{"id": "example/model", "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"}}]}),
        encoding="utf-8",
    )
    result = run_chat_preflight(
        PreflightContext(
            model="example/model",
            messages=[{"role": "user", "content": "hello there"}],
            rates_path=rates,
            max_tokens=10,
        )
    )
    assert result["requires_confirmation"] is True
    check = result["checks"][0]
    assert check["id"] == "cost-confirmation"
    assert "You are about to send" in check["message"]
    assert check["data"]["estimated_input_tokens"] > 0
    assert check["data"]["estimated_max_total_cost_usd"] is not None


def test_starter_model_catalog_has_dropdown_depth():
    from apexdev.llm.model_catalog import STARTER_MODELS, compact_model_options, rows_from_snapshot, starter_models_snapshot

    snapshot = starter_models_snapshot()
    rows = rows_from_snapshot(snapshot)
    options = compact_model_options(rows, limit=100)
    assert len(STARTER_MODELS) >= 45
    assert len(options) >= 45
    assert any(row["id"].startswith("anthropic/") for row in options)
    assert any(row["id"].startswith("openai/") for row in options)
    assert all("pricing" in row for row in options[:45])


def test_chat_preflight_uses_bundled_rates_when_snapshot_missing(tmp_path):
    from apexdev.llm.preflight import PreflightContext, run_chat_preflight

    missing_rates = tmp_path / "missing.openrouter.models.json"
    result = run_chat_preflight(
        PreflightContext(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "hello there"}],
            rates_path=missing_rates,
            max_tokens=10,
        )
    )
    check = result["checks"][0]
    assert "unknown amount" not in check["message"]
    assert check["data"]["pricing_source"] == "bundled-starter-catalog"
    assert check["data"]["used_seed_fallback"] is True
    assert check["data"]["estimated_max_total_cost_usd"] is not None
    assert check["data"]["missing_pricing"] == []


def test_chat_preflight_uses_bundled_rates_when_local_snapshot_lacks_model(tmp_path):
    from apexdev.llm.preflight import PreflightContext, run_chat_preflight

    old_rates = tmp_path / "old.openrouter.models.json"
    old_rates.write_text(json.dumps({"data": [{"id": "other/model", "pricing": {"prompt": "1", "completion": "1"}}]}), encoding="utf-8")
    result = run_chat_preflight(
        PreflightContext(
            model="anthropic/claude-sonnet-4",
            messages=[{"role": "user", "content": "hello there"}],
            rates_path=old_rates,
            max_tokens=10,
        )
    )
    check = result["checks"][0]
    assert "unknown amount" not in check["message"]
    assert check["data"]["pricing_source"] == "bundled-starter-catalog"
    assert check["data"]["used_seed_fallback"] is True
    assert check["data"]["missing_pricing"] == []


def test_chat_preflight_treats_dynamic_negative_router_pricing_as_unknown(tmp_path):
    from apexdev.llm.preflight import PreflightContext, run_chat_preflight

    result = run_chat_preflight(
        PreflightContext(
            model="openrouter/auto",
            messages=[{"role": "user", "content": "hello there"}],
            rates_path=tmp_path / "missing.json",
            max_tokens=10,
        )
    )
    check = result["checks"][0]
    assert "unknown amount" in check["message"] or "pricing is incomplete" in check["message"]
    assert any("dynamic" in item for item in check["data"]["missing_pricing"])
    assert "-" not in (check["data"]["estimated_max_total_cost_usd"] or "")
