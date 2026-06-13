from __future__ import annotations

# Default blocked-affordance template assets.
ACTIONS = [{'text': 'reach', 'cost': 1, 'tags': {'controlled', 'neutral'}}, {'text': 'fumble', 'cost': 1, 'tags': {'impaired', 'concussion'}}, {'text': 'grab', 'cost': 1, 'tags': {'forceful', 'anger'}}, {'text': 'shove', 'cost': 1, 'tags': {'forceful', 'crude', 'anger'}}, {'text': 'cover my face', 'cost': 3, 'tags': {'pain', 'protective', 'overwhelm'}}]

PROPS = [{'text': 'hand', 'cost': 1, 'tags': {'neutral'}}, {'text': 'sleeve', 'cost': 1, 'tags': {'soft', 'protective'}}, {'text': 'good arm', 'cost': 2, 'tags': {'injured', 'body_aware'}}, {'text': 'shaking hand', 'cost': 2, 'tags': {'impaired', 'anxiety'}}, {'text': 'bloody fingers', 'cost': 2, 'tags': {'injured', 'raw'}}]

def atoms_by_tag(tag: str) -> dict[str, list[dict]]:
    return {
        "actions": [a for a in ACTIONS if tag in a.get("tags", set())],
        "props": [p for p in PROPS if tag in p.get("tags", set())],
    }
