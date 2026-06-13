from __future__ import annotations
import random, re
from collections import Counter, defaultdict
from ..core.models import Conversation, Message
from .config import HOT_ATTRACTORS, HIDDEN_OPERATION_PATTERNS, SIDE_MARKERS, NoticingConfig
from .fragments import Fragment

def split_candidate_fragments(message: Message, config: NoticingConfig) -> list[Fragment]:
    if message.role not in {"user", "assistant"}:
        return []
    parts = [p.strip() for p in re.split(r"\n{2,}|(?<=[.!?])\s+(?=[A-Z\"“])", message.content) if p.strip()]
    out = []
    for part in parts:
        wc = len(part.split())
        if config.min_words <= wc <= config.max_words:
            out.append(Fragment.from_message(message, part))
    return out

def label_operations(text: str) -> list[str]:
    lower = text.lower()
    labels = []
    for label, patterns in HIDDEN_OPERATION_PATTERNS.items():
        if any(re.search(p, lower) for p in patterns):
            labels.append(label)
    return labels or ["unlabeled_operation"]

def find_hot_attractors(text: str) -> list[str]:
    lower = text.lower()
    return [h for h in HOT_ATTRACTORS if h in lower]

def find_side_markers(text: str) -> list[str]:
    lower = text.lower()
    return [m for m in SIDE_MARKERS if m in lower]

def score_fragment(fragment: Fragment, config: NoticingConfig) -> Fragment:
    words = len(fragment.text.split())
    role_weight = config.role_weights.get(fragment.role, 1.0)
    content_weight = config.content_type_weights.get(fragment.content_type, 1.0)
    fragment.operations = label_operations(fragment.text)
    fragment.hot_attractors = find_hot_attractors(fragment.text)
    fragment.side_markers = find_side_markers(fragment.text)
    score = (1 + min(words, 80) / 25) * role_weight * content_weight
    reasons = [f"words={words}", f"role={fragment.role}:{role_weight}", f"content_type={fragment.content_type}:{content_weight}"]
    if fragment.side_markers:
        score += config.side_marker_bonus * min(2, len(fragment.side_markers)); reasons.append("side_marker")
    if fragment.operations != ["unlabeled_operation"]:
        score += 1.0 + 0.25 * len(fragment.operations); reasons.append("hidden_operation")
    if fragment.hot_attractors:
        score -= config.hot_attractor_penalty * len(fragment.hot_attractors); reasons.append("hot_attractor_penalty")
    fragment.score = round(score, 4)
    fragment.reason_codes = reasons
    return fragment

def build_fragment_pool(conversations: list[Conversation], config: NoticingConfig | None = None) -> list[Fragment]:
    config = config or NoticingConfig()
    pool = []
    for conv in conversations:
        for msg in conv.messages:
            for frag in split_candidate_fragments(msg, config):
                pool.append(score_fragment(frag, config))
    return pool

def sample_fragments(pool: list[Fragment], config: NoticingConfig | None = None) -> list[Fragment]:
    config = config or NoticingConfig()
    rng = random.Random(config.random_seed)
    pool = sorted(pool, key=lambda f: f.score + rng.random() * 0.01, reverse=True)
    chosen, by_conv = [], Counter()
    for frag in pool:
        if by_conv[frag.conversation_id] >= config.max_per_conversation:
            continue
        chosen.append(frag)
        by_conv[frag.conversation_id] += 1
        if len(chosen) >= config.max_fragments:
            break
    return chosen

def cluster_by_operation(fragments: list[Fragment]) -> dict[str, list[Fragment]]:
    clusters = defaultdict(list)
    for frag in fragments:
        for op in frag.operations:
            clusters[op].append(frag)
    return dict(clusters)

def generate_packet(conversations: list[Conversation], config: NoticingConfig | None = None) -> dict:
    config = config or NoticingConfig()
    pool = build_fragment_pool(conversations, config)
    chosen = sample_fragments(pool, config)
    clusters = cluster_by_operation(chosen)
    operation, cluster = max(clusters.items(), key=lambda kv: (len(kv[1]), sum(f.score for f in kv[1])), default=("empty", []))
    return {"operation": operation, "fragment_count": len(chosen), "cluster_size": len(cluster), "fragments": [fragment_to_dict(f) for f in chosen], "cluster_fragments": [fragment_to_dict(f) for f in cluster]}

def fragment_to_dict(f: Fragment) -> dict:
    return {"id": f.id, "conversation_id": f.conversation_id, "message_id": f.message_id, "title": f.title, "role": f.role, "content_type": f.content_type, "text": f.text, "operations": f.operations, "hot_attractors": f.hot_attractors, "side_markers": f.side_markers, "score": f.score, "reason_codes": f.reason_codes}
