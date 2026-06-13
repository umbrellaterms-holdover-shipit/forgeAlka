from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .components import Component

@dataclass(slots=True)
class Rule:
    name: str
    when: list[str]
    then: list[str]

@dataclass(slots=True)
class RuleResult:
    rule: str
    component_id: str
    actions: list[str]
    facts: dict[str, Any]

def parse_rule(text: str) -> Rule:
    name = "unnamed"
    whens, thens = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("defrule"):
            name = line.split(maxsplit=1)[1].strip()
        elif line.startswith("when "):
            whens.append(line[5:].strip())
        elif line.startswith("then "):
            thens.append(line[5:].strip())
    return Rule(name, whens, thens)

def _condition_matches(component: Component, condition: str) -> bool:
    if " contains " in condition:
        field, value = condition.split(" contains ", 1)
        value = value.strip().strip('"').strip("'")
        target = getattr(component, field.strip(), component.attributes.get(field.strip(), ""))
        return value.lower() in str(target).lower()
    if "==" in condition:
        field, value = condition.split("==", 1)
        value = value.strip().strip('"').strip("'")
        target = getattr(component, field.strip(), component.attributes.get(field.strip(), ""))
        return str(target) == value
    if "!=" in condition:
        field, value = condition.split("!=", 1)
        value = value.strip().strip('"').strip("'")
        target = getattr(component, field.strip(), component.attributes.get(field.strip(), ""))
        return str(target) != value
    return False

class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None):
        self.rules = rules or []

    def add_rule(self, rule: Rule | str) -> None:
        self.rules.append(parse_rule(rule) if isinstance(rule, str) else rule)

    def evaluate(self, root: Component) -> list[RuleResult]:
        results = []
        for component in root.walk():
            for rule in self.rules:
                if all(_condition_matches(component, cond) for cond in rule.when):
                    results.append(RuleResult(rule.name, component.id, rule.then, {"kind": component.kind, **component.attributes}))
        return results
