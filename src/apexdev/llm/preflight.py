from __future__ import annotations

"""Composable preflight checks for LLM requests.

The chat UI asks this module for permission-shaped information before it sends a
live request. Checks are deliberately registry-based so cost confirmation is not
hard-coded into the React button. Add another function to CHAT_PREFLIGHT_CHECKS
and it joins the ritual.
"""

from dataclasses import dataclass, asdict
from decimal import Decimal
from math import ceil
from pathlib import Path
from typing import Any, Callable, Mapping

from .costs import format_money, rate_card_for_model_with_seed_fallback


@dataclass(frozen=True)
class PreflightContext:
    model: str
    messages: list[dict[str, Any]]
    rates_path: Path | None = None
    max_tokens: int | None = None
    wire_format: str = "auto"


@dataclass(frozen=True)
class PreflightCheck:
    id: str
    level: str
    message: str
    ok: bool = True
    requires_confirmation: bool = False
    data: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["data"] = dict(self.data or {})
        return row


CheckFunction = Callable[[PreflightContext], PreflightCheck | list[PreflightCheck] | None]


def _text_from_content(content: Any) -> str:
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
        return "\n".join(parts)
    return ""


def estimate_text_tokens(text: str) -> int:
    """Cheap local token estimate.

    This intentionally avoids provider tokenizer dependencies. It is a billing
    warning estimate, not an invoice. The formula combines character and word
    estimates and takes the larger value to avoid being too optimistic.
    """
    stripped = text.strip()
    if not stripped:
        return 0
    char_estimate = ceil(len(stripped) / 4)
    word_estimate = ceil(len(stripped.split()) * 1.35)
    return max(char_estimate, word_estimate, 1)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate input tokens for a role/content message list."""
    total = 0
    for message in messages:
        total += 4  # approximate role/message framing overhead
        total += estimate_text_tokens(_text_from_content(message.get("content")))
    return total


def _money_decimal(value: Decimal | None) -> str | None:
    return None if value is None else format_money(value)


def _known_nonnegative_price(value: Decimal | None) -> Decimal | None:
    """Return a usable price or None for missing/dynamic sentinel values."""
    if value is None or value < 0:
        return None
    return value


def cost_confirmation_check(ctx: PreflightContext) -> PreflightCheck:
    """Estimate input/output cost and produce the confirmation prompt."""
    input_tokens = estimate_message_tokens(ctx.messages)
    output_tokens = max(ctx.max_tokens or 0, 0)
    data: dict[str, Any] = {
        "model": ctx.model,
        "estimated_input_tokens": input_tokens,
        "max_output_tokens": output_tokens,
        "rates_path": str(ctx.rates_path) if ctx.rates_path else None,
        "estimator": "local chars/words heuristic",
    }

    input_cost: Decimal | None = None
    max_output_cost: Decimal | None = None
    request_cost: Decimal | None = None
    total_cost: Decimal | None = None
    missing: list[str] = []

    pricing, pricing_source, used_seed_fallback = rate_card_for_model_with_seed_fallback(ctx.rates_path, ctx.model)
    data["pricing_source"] = pricing_source
    data["used_seed_fallback"] = used_seed_fallback
    prompt_price_raw = pricing.get("prompt")
    completion_price_raw = pricing.get("completion")
    request_price_raw = pricing.get("request")
    prompt_price = _known_nonnegative_price(prompt_price_raw)
    completion_price = _known_nonnegative_price(completion_price_raw)
    request_price = _known_nonnegative_price(request_price_raw)
    if prompt_price is None:
        missing.append("prompt" if prompt_price_raw is None else "prompt(dynamic)")
    else:
        input_cost = Decimal(input_tokens) * prompt_price
    if output_tokens:
        if completion_price is None:
            missing.append("completion" if completion_price_raw is None else "completion(dynamic)")
        else:
            max_output_cost = Decimal(output_tokens) * completion_price
    if request_price is not None:
        request_cost = request_price
    known_parts = [p for p in (input_cost, max_output_cost, request_cost) if p is not None]
    if known_parts:
        total_cost = sum(known_parts, Decimal("0"))

    data.update(
        {
            "estimated_input_cost_usd": _money_decimal(input_cost),
            "estimated_max_output_cost_usd": _money_decimal(max_output_cost),
            "request_cost_usd": _money_decimal(request_cost),
            "estimated_max_total_cost_usd": _money_decimal(total_cost),
            "missing_pricing": missing,
        }
    )

    if total_cost is None:
        display_cost = "an unknown amount because pricing is missing"
    else:
        display_cost = f"about ${format_money(total_cost)}"
    message = f"You are about to send {input_tokens} estimated input tokens which will cost {display_cost}. Continue?"
    if output_tokens and max_output_cost is not None:
        message = (
            f"You are about to send {input_tokens} estimated input tokens and allow up to "
            f"{output_tokens} output tokens, which will cost at most about ${format_money(total_cost or Decimal('0'))}. Continue?"
        )
    elif output_tokens:
        message = (
            f"You are about to send {input_tokens} estimated input tokens and allow up to "
            f"{output_tokens} output tokens, but pricing is incomplete. Continue?"
        )

    level = "warning" if missing else "confirm"
    return PreflightCheck(
        id="cost-confirmation",
        level=level,
        message=message,
        ok=True,
        requires_confirmation=True,
        data=data,
    )


CHAT_PREFLIGHT_CHECKS: list[CheckFunction] = [cost_confirmation_check]


def run_chat_preflight(ctx: PreflightContext, checks: list[CheckFunction] | None = None) -> dict[str, Any]:
    """Run the registered preflight checks and return JSON-ready data."""
    rows: list[PreflightCheck] = []
    for fn in checks or CHAT_PREFLIGHT_CHECKS:
        result = fn(ctx)
        if result is None:
            continue
        if isinstance(result, list):
            rows.extend(result)
        else:
            rows.append(result)
    return {
        "ok": all(row.ok for row in rows),
        "requires_confirmation": any(row.requires_confirmation for row in rows),
        "checks": [row.to_dict() for row in rows],
        "confirmation_message": "\n".join(row.message for row in rows if row.requires_confirmation),
    }
