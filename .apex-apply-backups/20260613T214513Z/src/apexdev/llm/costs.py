from __future__ import annotations

"""OpenRouter-style rate files and offline cost estimates."""

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping
import json

TOKEN_FIELDS = {
    "prompt": ("prompt_tokens", "input_tokens"),
    "completion": ("completion_tokens", "output_tokens"),
    "internal_reasoning": ("reasoning_tokens", "internal_reasoning_tokens"),
}
UNIT_FIELDS = {
    "request": ("requests", "request_count"),
    "image": ("images", "image_count"),
    "web_search": ("web_searches", "web_search_count"),
    "input_cache_read": ("cache_read_tokens", "input_cache_read_tokens"),
    "input_cache_write": ("cache_write_tokens", "input_cache_write_tokens"),
}


@dataclass(frozen=True)
class RequestCost:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 1
    total_usd: Decimal = Decimal("0")
    missing_pricing: list[str] | None = None
    source_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["total_usd"] = format_money(self.total_usd)
        return row


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def format_money(value: Decimal, places: str = "0.00000001") -> str:
    q = value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    digits = abs(Decimal(places).as_tuple().exponent)
    return f"{q:.{digits}f}"


def _normalize_models_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        if isinstance(data.get("models"), list):
            return data["models"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("data"), dict) and isinstance(data["data"].get("data"), list):
            return data["data"]["data"]
    if isinstance(data, list):
        return data
    raise ValueError("Rate file must contain OpenRouter model data under `data`, `models`, or as a list")


def load_rate_card(path: str | Path) -> dict[str, dict[str, Decimal]]:
    """Load model pricing from an OpenRouter `/models` snapshot or compact rate file.

    The returned mapping is `model_id -> pricing_field -> Decimal USD per unit`.
    OpenRouter's model API reports pricing fields as strings; this function also
    accepts numeric manual override files with the same keys.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = _normalize_models_payload(raw)
    rates: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        model_id = row.get("id") or row.get("model") or row.get("name")
        pricing = row.get("pricing") or row.get("rates") or {}
        if not model_id or not isinstance(pricing, dict):
            continue
        rates[str(model_id)] = {str(k): _decimal(v) for k, v in pricing.items()}
    return rates


def _dig(data: Mapping[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return None
        cur = cur[part]
    return cur


def request_model(record: Mapping[str, Any]) -> str:
    for key in ("model", "response.model", "request.model"):
        value = _dig(record, key)
        if value:
            return str(value)
    raise ValueError("Request record is missing a model field")


def request_usage(record: Mapping[str, Any]) -> dict[str, int]:
    usage = record.get("usage") if isinstance(record.get("usage"), Mapping) else record
    result: dict[str, int] = {}
    for canonical, aliases in {**TOKEN_FIELDS, **UNIT_FIELDS}.items():
        for alias in aliases:
            value = usage.get(alias) if isinstance(usage, Mapping) else None
            if value is not None:
                result[canonical] = int(value)
                break
    result.setdefault("request", int(record.get("requests", record.get("request_count", 1)) or 1))
    return result


def cost_one(record: Mapping[str, Any], rates: Mapping[str, Mapping[str, Decimal]], *, source_index: int | None = None) -> RequestCost:
    model = request_model(record)
    usage = request_usage(record)
    pricing = rates.get(model, {})
    total = Decimal("0")
    missing: list[str] = []
    for field in sorted(set(TOKEN_FIELDS) | set(UNIT_FIELDS)):
        qty = usage.get(field, 0)
        if not qty:
            continue
        price = pricing.get(field)
        if price is None:
            missing.append(field)
            continue
        total += Decimal(qty) * price
    return RequestCost(
        model=model,
        prompt_tokens=usage.get("prompt", 0),
        completion_tokens=usage.get("completion", 0),
        reasoning_tokens=usage.get("internal_reasoning", 0),
        requests=usage.get("request", 1),
        total_usd=total,
        missing_pricing=missing,
        source_index=source_index,
    )


def _iter_json_records(path: str | Path) -> Iterable[dict[str, Any]]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)
        return
    data = json.loads(text)
    if isinstance(data, list):
        for item in data:
            yield item
    elif isinstance(data, dict) and isinstance(data.get("requests"), list):
        for item in data["requests"]:
            yield item
    else:
        yield data


def estimate_request_costs(rates_path: str | Path, requests_path: str | Path) -> dict[str, Any]:
    """Estimate cost for JSON/JSONL request records using a local rate card."""
    rates = load_rate_card(rates_path)
    rows = [cost_one(record, rates, source_index=i) for i, record in enumerate(_iter_json_records(requests_path))]
    by_model: dict[str, dict[str, Any]] = {}
    total = Decimal("0")
    for row in rows:
        total += row.total_usd
        bucket = by_model.setdefault(row.model, {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_usd": Decimal("0")})
        bucket["requests"] += row.requests
        bucket["prompt_tokens"] += row.prompt_tokens
        bucket["completion_tokens"] += row.completion_tokens
        bucket["reasoning_tokens"] += row.reasoning_tokens
        bucket["total_usd"] += row.total_usd
    serial_by_model = {
        model: {**{k: v for k, v in values.items() if k != "total_usd"}, "total_usd": format_money(values["total_usd"])}
        for model, values in sorted(by_model.items())
    }
    return {
        "request_count": len(rows),
        "total_usd": format_money(total),
        "by_model": serial_by_model,
        "requests": [row.to_dict() for row in rows],
    }


def write_cost_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return out
