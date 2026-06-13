from __future__ import annotations

"""Helpers for local OpenRouter-style rate files."""

from pathlib import Path
from typing import Any
import json

from .model_catalog import STARTER_MODELS_SOURCE, starter_models_snapshot, write_starter_models


def write_example_rates(path: str | Path) -> Path:
    """Write a tiny manual rate file matching the OpenRouter pricing shape."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "source": "manual example; replace with apex rates seed or apex models refresh",
        "data": [
            {
                "id": "example/model",
                "pricing": {
                    "prompt": "0.000000001",
                    "completion": "0.000000002",
                    "request": "0",
                    "image": "0",
                    "web_search": "0",
                    "internal_reasoning": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0",
                },
            }
        ],
    }
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def write_seed_rates(path: str | Path) -> Path:
    """Write the bundled starter OpenRouter catalog/rate card."""
    return write_starter_models(path)


def seed_rates_info() -> dict[str, Any]:
    snapshot = starter_models_snapshot()
    return {"source": STARTER_MODELS_SOURCE, "model_count": len(snapshot["data"])}
