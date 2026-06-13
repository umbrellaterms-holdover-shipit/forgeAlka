from __future__ import annotations
from jinja2 import Environment, BaseLoader

PACKET_TEMPLATE = '''# Noticing Packet

Seed operation: **{{ packet.operation }}**

Fragments selected: {{ packet.fragment_count }}
Cluster size: {{ packet.cluster_size }}

## Cluster evidence
{% for f in packet.cluster_fragments %}
### {{ loop.index }}. {{ f.title or f.conversation_id }} / {{ f.message_id }}
Score: {{ f.score }}
Operations: {{ f.operations|join(", ") }}
Reasons: {{ f.reason_codes|join(", ") }}

> {{ f.text | replace("\n", "\n> ") }}

{% endfor %}

## All selected fragments
{% for f in packet.fragments %}
- `{{ f.id }}` {{ f.title }} :: {{ f.text[:120] }}{% if f.text|length > 120 %}…{% endif %}
{% endfor %}
'''

def render_packet_markdown(packet: dict) -> str:
    return Environment(loader=BaseLoader(), autoescape=False).from_string(PACKET_TEMPLATE).render(packet=packet)
