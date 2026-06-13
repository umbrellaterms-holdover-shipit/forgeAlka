from __future__ import annotations

CLUSTER_KEYWORDS = {
    "Noticing engine and packet generator": ["noticing", "fragment", "packet", "hot attractor", "operation"],
    "Conversation traversal indexes": ["index", "spine", "postings", "quote anchor", "correction", "acceptance"],
    "Conversation analytics and semantic payload": ["analytics", "semantic payload", "output trend", "token", "role metrics"],
    "Document conversion suite": ["docx", "markdown", "pdf", "tex", "latex", "equation"],
    "Spreadsheet/CSV/chart outputs": ["csv", "xlsx", "spreadsheet", "chart", "rolling"],
    "Flux prompt/dataset generator": ["flux", "prompt", "taxonomy", "salt", "jsonl"],
    "Chatter/TTS/audio pipeline": ["tts", "chatter", "audio", "speaker", "schedule"],
    "Structured dialogue/rules engine": ["clips", "rule", "component", "affordance", "dialogue"],
    "Responses/Agents API orchestration model": ["responses", "agents", "payload", "adapter", "simulator"],
    "Question/Knot generator": ["question", "knot", "random walk", "local search", "echo"],
    "Noticing benchmark kit": ["benchmark", "evidence pack", "precision", "recall", "rubric"],
}


def classify_text(text: str) -> tuple[str, float]:
    lower = text.lower()
    best = ("other", 0.0)
    for cluster, keywords in CLUSTER_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            score = min(0.95, hits / max(3, len(keywords)) + 0.35)
            if score > best[1]:
                best = (cluster, score)
    return best
