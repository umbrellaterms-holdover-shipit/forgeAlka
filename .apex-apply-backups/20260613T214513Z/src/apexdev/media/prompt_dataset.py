from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from jinja2 import Template
import hashlib, json, itertools
from .flux_catalogs import default_catalog

@dataclass(slots=True)
class FluxPrompt:
    id: str
    prompt: str
    components: dict[str, str]
    salt: str = ""

DEFAULT_TEMPLATE = "{{ style }} of {{ person }} wearing {{ outfit }}, {{ pose }}. The scene is {{ location }}. {{ prop }} is visible. {{ lighting }}."

def stable_id(parts: dict[str, str], salt: str = "") -> str:
    return hashlib.sha1(json.dumps({"parts": parts, "salt": salt}, sort_keys=True).encode()).hexdigest()[:16]

def compose_prompt(parts: dict[str, str], template: str = DEFAULT_TEMPLATE, salt: str = "") -> FluxPrompt:
    return FluxPrompt(stable_id(parts, salt), Template(template).render(**parts), parts, salt)

def expand_grid(catalog: dict[str, list[str]], template: str = DEFAULT_TEMPLATE, salt: str = "") -> list[FluxPrompt]:
    keys = list(catalog)
    return [compose_prompt(dict(zip(keys, combo)), template, salt) for combo in itertools.product(*(catalog[k] for k in keys))]

def write_jsonl(prompts: list[FluxPrompt], path: str | Path) -> Path:
    out = Path(path)
    with out.open("w", encoding="utf-8") as f:
        for p in prompts:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
    return out


def generate_default_grid(limit: int | None = None, salt: str = "default-flux-catalog") -> list[FluxPrompt]:
    """Generate prompts from the default Flux catalog.

    This streams the cartesian product and stops at ``limit`` when supplied,
    so callers can safely sample from large catalogs without materializing
    millions of prompt combinations.
    """
    catalog = default_catalog()
    keys = list(catalog)
    prompts: list[FluxPrompt] = []
    for combo in itertools.product(*(catalog[k] for k in keys)):
        parts = dict(zip(keys, combo))
        prompts.append(compose_prompt(parts, salt=salt))
        if limit is not None and len(prompts) >= limit:
            break
    return prompts
