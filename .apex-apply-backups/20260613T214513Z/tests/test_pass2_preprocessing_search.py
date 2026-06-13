from pathlib import Path
import json

from apexdev.core.loader import load_conversations
from apexdev.preprocessing.normalization import normalize_text, normalize_role
from apexdev.preprocessing.dedupe import dedupe_messages
from apexdev.preprocessing.code_windows import extract_code_windows
from apexdev.search.adapters import conversation_documents
from apexdev.search.index import build_search_index
from apexdev.conversations.sentence_preprocessor import preprocess_sentences, to_tsv
from apexdev.conversations.splitter import split_by_tokens
from apexdev.conversations.active_path import infer_active_path
from apexdev.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_conversation.json"


def test_preprocessing_normalization_and_dedupe():
    assert normalize_text("  A   B \r\n C  ") == "A B\nC"
    assert normalize_role("Human") == "user"
    convs = load_conversations(FIXTURE)
    result = dedupe_messages(convs)
    assert result.conversations[0].messages
    assert result.dropped_message_ids == []


def test_code_windows_and_search():
    convs = load_conversations(FIXTURE)
    windows = extract_code_windows(convs, radius=1)
    assert windows and windows[0].center_message_id == "a1"
    docs = conversation_documents(convs)
    idx = build_search_index(docs)
    results = idx.search("wrong cost placement")
    assert results[0][0].id == "u1"


def test_sentence_preprocessing_chunks_active_path():
    conv = load_conversations(FIXTURE)[0]
    rows = preprocess_sentences([conv])
    assert any(r.message_id == "u1" for r in rows)
    assert to_tsv(rows).startswith("sentence_id\tconversation_id")
    chunks = split_by_tokens(conv, max_tokens=12, overlap_messages=0)
    assert len(chunks) >= 2
    path = infer_active_path(conv)
    assert path.message_ids == ["u1", "a1", "u2"]


def test_cli_pass2_commands(tmp_path):
    pre = tmp_path / "pre.json"
    main(["preprocess", "--input", str(FIXTURE), "--out", str(pre)])
    assert "conversations" in json.loads(pre.read_text())

    cw = tmp_path / "windows.json"
    main(["code-windows", "--input", str(FIXTURE), "--out", str(cw)])
    assert json.loads(cw.read_text())

    sr = tmp_path / "search.json"
    main(["search", "--input", str(FIXTURE), "--query", "wrong cost", "--out", str(sr)])
    assert json.loads(sr.read_text())[0]["id"] == "u1"

    sent = tmp_path / "sent.tsv"
    main(["sentences", "--input", str(FIXTURE), "--out", str(sent)])
    assert sent.read_text().splitlines()[0].startswith("sentence_id")

    chunks = tmp_path / "chunks.json"
    main(["chunks", "--input", str(FIXTURE), "--out", str(chunks), "--max-tokens", "12"])
    assert json.loads(chunks.read_text())
