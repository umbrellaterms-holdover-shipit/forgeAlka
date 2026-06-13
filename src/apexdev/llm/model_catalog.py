from __future__ import annotations

"""Bundled starter model catalog for OpenRouter UX.

This is not the billing source of truth. It is a useful first-run catalog so the
web UI can show a real dropdown before the user refreshes live OpenRouter rates.
Run `apex models refresh` to replace this seed with the current catalog.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping
import json
import time

STARTER_MODELS_SOURCE = "starter seed from OpenRouter public model/API pages; refresh before billing-sensitive use"

# Pricing values are USD per token, matching the OpenRouter /api/v1/models shape.
# The UI displays them as USD per 1M tokens because humans deserve mercy.
STARTER_MODELS: list[dict[str, Any]] = [
    {"id": "anthropic/claude-sonnet-4.6", "name": "Anthropic: Claude Sonnet 4.6", "context_length": 1_000_000, "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "anthropic/claude-sonnet-4", "name": "Anthropic: Claude Sonnet 4", "context_length": 1_000_000, "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "anthropic/claude-opus-4.8", "name": "Anthropic: Claude Opus 4.8", "context_length": 1_000_000, "pricing": {"prompt": "0.000005", "completion": "0.000025", "web_search": "0.01", "input_cache_read": "0.0000005", "input_cache_write": "0.00000625"}, "supported_parameters": ["max_tokens", "tools", "reasoning"]},
    {"id": "anthropic/claude-opus-4.8-fast", "name": "Anthropic: Claude Opus 4.8 Fast", "context_length": 1_000_000, "pricing": {"prompt": "0.00001", "completion": "0.00005", "web_search": "0.01", "input_cache_read": "0.000001", "input_cache_write": "0.0000125"}, "supported_parameters": ["max_tokens", "tools", "reasoning"]},
    {"id": "anthropic/claude-fable-5", "name": "Anthropic: Claude Fable 5", "context_length": 1_000_000, "pricing": {"prompt": "0.00001", "completion": "0.00005", "web_search": "0.01", "input_cache_read": "0.000001", "input_cache_write": "0.0000125"}, "supported_parameters": ["max_tokens", "tools", "reasoning"]},
    {"id": "~anthropic/claude-fable-latest", "name": "Anthropic: Claude Fable Latest Alias", "context_length": 1_000_000, "pricing": {"prompt": "0.00001", "completion": "0.00005", "web_search": "0.01", "input_cache_read": "0.000001", "input_cache_write": "0.0000125"}, "supported_parameters": ["max_tokens", "tools", "reasoning"]},
    {"id": "anthropic/claude-3.7-sonnet", "name": "Anthropic: Claude 3.7 Sonnet", "context_length": 200_000, "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "anthropic/claude-3.5-haiku", "name": "Anthropic: Claude 3.5 Haiku", "context_length": 200_000, "pricing": {"prompt": "0.0000008", "completion": "0.000004"}, "supported_parameters": ["max_tokens", "temperature"]},
    {"id": "openai/gpt-5.2-codex", "name": "OpenAI: GPT-5.2-Codex", "context_length": 400_000, "pricing": {"prompt": "0.00000175", "completion": "0.000014", "web_search": "0.01", "input_cache_read": "0.000000175"}, "supported_parameters": ["max_tokens", "reasoning", "tools"]},
    {"id": "openai/gpt-4o", "name": "OpenAI: GPT-4o", "context_length": 128_000, "pricing": {"prompt": "0.0000025", "completion": "0.00001"}, "supported_parameters": ["max_tokens", "temperature", "tools", "response_format"]},
    {"id": "openai/gpt-4o-mini", "name": "OpenAI: GPT-4o Mini", "context_length": 128_000, "pricing": {"prompt": "0.00000015", "completion": "0.0000006"}, "supported_parameters": ["max_tokens", "temperature", "tools", "response_format"]},
    {"id": "openai/gpt-4.1", "name": "OpenAI: GPT-4.1", "context_length": 1_047_576, "pricing": {"prompt": "0.000002", "completion": "0.000008"}, "supported_parameters": ["max_tokens", "temperature", "tools", "response_format"]},
    {"id": "openai/gpt-4.1-mini", "name": "OpenAI: GPT-4.1 Mini", "context_length": 1_047_576, "pricing": {"prompt": "0.0000004", "completion": "0.0000016"}, "supported_parameters": ["max_tokens", "temperature", "tools", "response_format"]},
    {"id": "openai/gpt-4.1-nano", "name": "OpenAI: GPT-4.1 Nano", "context_length": 1_047_576, "pricing": {"prompt": "0.0000001", "completion": "0.0000004"}, "supported_parameters": ["max_tokens", "temperature", "response_format"]},
    {"id": "openai/gpt-audio", "name": "OpenAI: GPT Audio", "context_length": 128_000, "pricing": {"prompt": "0.0000025", "completion": "0.00001", "audio": "0.000032"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "openai/gpt-audio-mini", "name": "OpenAI: GPT Audio Mini", "context_length": 128_000, "pricing": {"prompt": "0.0000006", "completion": "0.0000024", "audio": "0.0000006"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "google/gemini-2.5-pro", "name": "Google: Gemini 2.5 Pro", "context_length": 1_048_576, "pricing": {"prompt": "0.00000125", "completion": "0.00001"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "google/gemini-2.5-flash", "name": "Google: Gemini 2.5 Flash", "context_length": 1_048_576, "pricing": {"prompt": "0.0000003", "completion": "0.0000025"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "google/gemini-2.5-flash-lite", "name": "Google: Gemini 2.5 Flash Lite", "context_length": 1_048_576, "pricing": {"prompt": "0.0000001", "completion": "0.0000004", "image": "0.0000001", "audio": "0.0000003", "web_search": "0.014", "internal_reasoning": "0.0000004", "input_cache_read": "0.00000001", "input_cache_write": "0.00000008333333333333334"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "google/gemini-3.5-flash", "name": "Google: Gemini 3.5 Flash", "context_length": 1_000_000, "pricing": {"prompt": "0.0000003", "completion": "0.0000025"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "x-ai/grok-build-0.1", "name": "xAI: Grok Build 0.1", "context_length": 256_000, "pricing": {"prompt": "0.000001", "completion": "0.000002", "web_search": "0.005", "input_cache_read": "0.0000002"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "x-ai/grok-4", "name": "xAI: Grok 4", "context_length": 256_000, "pricing": {"prompt": "0.000003", "completion": "0.000015"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "qwen/qwen3.7-max", "name": "Qwen: Qwen3.7 Max", "context_length": 1_000_000, "pricing": {"prompt": "0.00000125", "completion": "0.00000375", "input_cache_read": "0.00000025", "input_cache_write": "0.0000015625"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "qwen/qwen3.7-plus", "name": "Qwen: Qwen3.7 Plus", "context_length": 1_000_000, "pricing": {"prompt": "0.00000032", "completion": "0.00000128", "input_cache_read": "0.000000064", "input_cache_write": "0.0000004"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "qwen/qwen3-coder", "name": "Qwen: Qwen3 Coder 480B A35B", "context_length": 1_048_576, "pricing": {"prompt": "0.00000022", "completion": "0.0000018"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "qwen/qwen3-coder:free", "name": "Qwen: Qwen3 Coder 480B A35B Free", "context_length": 1_048_576, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "qwen/qwen3-235b-a22b-thinking-2507", "name": "Qwen: Qwen3 235B A22B Thinking 2507", "context_length": 262_144, "pricing": {"prompt": "0.0000001", "completion": "0.0000001", "input_cache_read": "0.0000001"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "qwen/qwen3-235b-a22b-2507", "name": "Qwen: Qwen3 235B A22B Instruct 2507", "context_length": 262_144, "pricing": {"prompt": "0.00000009", "completion": "0.0000001"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "moonshotai/kimi-k2.7-code", "name": "MoonshotAI: Kimi K2.7 Code", "context_length": 262_144, "pricing": {"prompt": "0.00000075", "completion": "0.0000035", "input_cache_read": "0.00000016"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "moonshotai/kimi-k2", "name": "MoonshotAI: Kimi K2 0711", "context_length": 131_072, "pricing": {"prompt": "0.0000006", "completion": "0.0000025"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "minimax/minimax-m3", "name": "MiniMax: MiniMax M3", "context_length": 1_048_576, "pricing": {"prompt": "0.0000003", "completion": "0.0000012", "input_cache_read": "0.00000006"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "minimax/minimax-m2.1", "name": "MiniMax: MiniMax M2.1", "context_length": 262_144, "pricing": {"prompt": "0.0000003", "completion": "0.0000012"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "minimax/minimax-m2-her", "name": "MiniMax: MiniMax M2-her", "context_length": 65_536, "pricing": {"prompt": "0.0000003", "completion": "0.0000012", "input_cache_read": "0.00000003"}, "supported_parameters": ["max_tokens", "temperature", "top_p"]},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b", "name": "NVIDIA: Nemotron 3 Ultra", "context_length": 1_000_000, "pricing": {"prompt": "0.0000005", "completion": "0.0000025", "input_cache_read": "0.00000015"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "NVIDIA: Nemotron 3 Ultra Free", "context_length": 1_000_000, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "nvidia/nemotron-3.5-content-safety:free", "name": "NVIDIA: Nemotron 3.5 Content Safety Free", "context_length": 128_000, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature", "reasoning"]},
    {"id": "z-ai/glm-4.7-flash", "name": "Z.ai: GLM 4.7 Flash", "context_length": 202_752, "pricing": {"prompt": "0.00000006", "completion": "0.0000004", "input_cache_read": "0.00000001"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "z-ai/glm-4.5", "name": "Z.ai: GLM 4.5", "context_length": 131_072, "pricing": {"prompt": "0.0000006", "completion": "0.0000022", "input_cache_read": "0.00000011"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "z-ai/glm-4.5-air", "name": "Z.ai: GLM 4.5 Air", "context_length": 131_072, "pricing": {"prompt": "0.000000125", "completion": "0.00000085", "input_cache_read": "0.00000006"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "bytedance-seed/seed-1.6", "name": "ByteDance Seed: Seed 1.6", "context_length": 262_144, "pricing": {"prompt": "0.00000025", "completion": "0.000002"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "bytedance-seed/seed-1.6-flash", "name": "ByteDance Seed: Seed 1.6 Flash", "context_length": 262_144, "pricing": {"prompt": "0.000000075", "completion": "0.0000003"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "bytedance/ui-tars-1.5-7b", "name": "ByteDance: UI-TARS 7B", "context_length": 128_000, "pricing": {"prompt": "0.0000001", "completion": "0.0000002", "input_cache_read": "0.0000001"}, "supported_parameters": ["max_tokens", "temperature"]},
    {"id": "stepfun/step-3.7-flash", "name": "StepFun: Step 3.7 Flash", "context_length": 256_000, "pricing": {"prompt": "0.0000002", "completion": "0.00000115", "input_cache_read": "0.00000004"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "upstage/solar-pro-3", "name": "Upstage: Solar Pro 3", "context_length": 128_000, "pricing": {"prompt": "0.00000015", "completion": "0.0000006", "input_cache_read": "0.000000015"}, "supported_parameters": ["max_tokens", "temperature", "tools", "reasoning"]},
    {"id": "writer/palmyra-x5", "name": "Writer: Palmyra X5", "context_length": 1_040_000, "pricing": {"prompt": "0.0000006", "completion": "0.000006"}, "supported_parameters": ["max_tokens", "temperature", "top_p"]},
    {"id": "liquid/lfm-2.5-1.2b-thinking:free", "name": "LiquidAI: LFM2.5 1.2B Thinking Free", "context_length": 32_768, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature", "reasoning"]},
    {"id": "liquid/lfm-2.5-1.2b-instruct:free", "name": "LiquidAI: LFM2.5 1.2B Instruct Free", "context_length": 32_768, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature"]},
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Meta: Llama 3.3 70B Instruct Free", "context_length": 131_072, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature"]},
    {"id": "openrouter/free", "name": "OpenRouter: Free Models Router", "context_length": 131_072, "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "openrouter/auto", "name": "OpenRouter: Auto Router", "context_length": 128_000, "pricing": {"prompt": "-1", "completion": "-1"}, "supported_parameters": ["max_tokens", "temperature", "tools"]},
    {"id": "switchpoint/router", "name": "Switchpoint Router", "context_length": 131_072, "pricing": {"prompt": "0.00000085", "completion": "0.0000034"}, "supported_parameters": ["max_tokens", "temperature", "reasoning"]},
]


def starter_models_snapshot() -> dict[str, Any]:
    return {"source": STARTER_MODELS_SOURCE, "created_at_unix": time.time(), "data": deepcopy(STARTER_MODELS)}


def write_starter_models(path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(starter_models_snapshot(), indent=2, sort_keys=True), encoding="utf-8")
    return out


def load_models_snapshot(path: str | Path | None = None, *, fallback_to_seed: bool = True) -> tuple[dict[str, Any], str]:
    if path:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), str(p)
        if not fallback_to_seed:
            raise FileNotFoundError(str(p))
    return starter_models_snapshot(), "bundled-starter-catalog"


def rows_from_snapshot(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: Any = snapshot.get("data", snapshot)
    if isinstance(rows, Mapping) and isinstance(rows.get("data"), list):
        rows = rows["data"]
    if not isinstance(rows, list):
        raise ValueError("models snapshot must contain a data list")
    return [row for row in rows if isinstance(row, dict)]


def compact_model_options(rows: Iterable[Mapping[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for row in rows:
        pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
        option = {
            "id": row.get("id"),
            "name": row.get("name") or row.get("id"),
            "context_length": row.get("context_length"),
            "pricing": dict(pricing or {}),
            "supported_parameters": list(row.get("supported_parameters") or []),
        }
        if option["id"]:
            options.append(option)
        if limit is not None and len(options) >= limit:
            break
    return options
