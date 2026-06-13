from __future__ import annotations
from dataclasses import dataclass, field

SIDE_MARKERS = ["also", "though", "actually", "by the way", "incidentally", "the funny thing", "notably", "for some reason", "wait", "no,", "but", "except", "the issue is", "what's missing", "the problem is", "this is wrong", "not quite", "right.", "cool."]
HOT_ATTRACTORS = ["truth under load", "invariant", "nyllabus", "derek", "good conduct", "audrey", "optima", "apex communicator", "brick", "kinetica", "noticing game", "false categories", "conversion boundary", "universal cost function", "constraint altitude", "human-scale priors", "anti-alibi", "office", "vba", "colonel", "surface as machinery"]
HIDDEN_OPERATION_PATTERNS = {
    "absence_signature": [r"\bmissing\b", r"\babsence\b", r"\bnot there\b", r"\binvisible\b", r"\bnegative space\b"],
    "wrong_cost_placement": [r"\bcost\b", r"\bexpensive\b", r"\bcheap\b", r"\binvoice\b", r"\btoo much work\b"],
    "routing_consequence": [r"\broute\b", r"\bpath\b", r"\bentry\b", r"\bthrough\b", r"\bleads\b"],
    "bluffable_test": [r"\btest\b", r"\bcheck\b", r"\bdiagnostic\b", r"\bprove\b", r"\bfails?\b"],
    "container_vs_property": [r"\bcontainer\b", r"\bwrapper\b", r"\bframe\b", r"\bproperty\b", r"\bcategory\b", r"\bhandle\b"],
    "protected_uncertainty": [r"\buncertain\b", r"\bunknown\b", r"\bnot know\b", r"\bleave open\b", r"\bambiguous\b"],
    "surface_as_actuator": [r"\bsurface\b", r"\bactuator\b", r"\binterface\b", r"\bhandle\b", r"\bbutton\b", r"\blever\b"],
    "compression_with_loss": [r"\bcompress\b", r"\bsummar", r"\bloss\b", r"\bprojection\b", r"\bcollapsed\b"],
}

@dataclass
class NoticingConfig:
    max_fragments: int = 24
    max_per_conversation: int = 4
    hot_attractor_penalty: float = 2.5
    side_marker_bonus: float = 1.5
    min_words: int = 8
    max_words: int = 90
    random_seed: int | None = None
    role_weights: dict[str, float] = field(default_factory=lambda: {"user": 1.35, "assistant": 0.8, "tool": 0.3})
    content_type_weights: dict[str, float] = field(default_factory=lambda: {"text": 1.0, "thoughts": 1.25, "reasoning_recap": 1.15, "multimodal_text": 1.1})
