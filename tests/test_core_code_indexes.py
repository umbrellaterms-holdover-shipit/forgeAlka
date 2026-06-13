from pathlib import Path
from apexdev.core.loader import load_conversations
from apexdev.code_inspection.code_signal_detector import detect_code_signal
from apexdev.code_inspection.snippet_extractor import extract_snippets
from apexdev.indexes.inverted import InvertedIndex
from apexdev.indexes.spines import build_spines, build_turn_index
from apexdev.indexes.correction_acceptance import detect_turn_signals, detect_artifact_requests

FIXTURE = Path(__file__).parent / "fixtures" / "sample_conversation.json"

def test_loader_preserves_metadata():
    conv = load_conversations(FIXTURE)[0]
    assert conv.id == "conv-1"
    assert conv.messages[0].id == "u1"
    assert conv.messages[0].source_file == "fixture.json"

def test_code_signal_and_snippets():
    conv = load_conversations(FIXTURE)[0]
    sig = detect_code_signal(conv.messages[1].content)
    assert sig.has_fence and sig.score >= 5
    snippets = extract_snippets(conv.messages[1].content)
    assert snippets[0].kind == "fenced" and "print" in snippets[0].text

def test_indexing_and_turn_signals():
    convs = load_conversations(FIXTURE)
    idx = InvertedIndex().build(convs)
    assert idx.search("missing path")[0].id == "u1"
    assert build_spines(convs)[0].message_ids == ["u1", "a1", "u2"]
    assert build_turn_index(convs)["a1"]["ordinal"] == 1
    assert any(s.kind == "acceptance" for s in detect_turn_signals(convs))
    assert any(a.marker == "pdf" for a in detect_artifact_requests(convs))
