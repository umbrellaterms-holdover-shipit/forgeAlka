from pathlib import Path
from apexdev.core.loader import load_conversations
from apexdev.noticing.config import NoticingConfig
from apexdev.noticing.engine import build_fragment_pool, generate_packet
from apexdev.noticing.packets import render_packet_markdown
from apexdev.analytics.role_metrics import role_counts, role_token_counts
from apexdev.analytics.semantic_payload import corpus_payload
from apexdev.analytics.output_trends import conversation_output_trend
from apexdev.analytics.charts import write_trend_svg
from apexdev.documents.markdown_tools import markdown_word_count, heading_outline
from apexdev.documents.equation_docs import EquationEntry, render_equation_glossary
from apexdev.documents.spreadsheets import write_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample_conversation.json"

def test_noticing_engine_and_packet():
    convs = load_conversations(FIXTURE)
    pool = build_fragment_pool(convs, NoticingConfig(max_fragments=10, min_words=3))
    assert any("absence_signature" in f.operations for f in pool)
    assert any("wrong_cost_placement" in f.operations for f in pool)
    md = render_packet_markdown(generate_packet(convs, NoticingConfig(max_fragments=3, min_words=3)))
    assert "# Noticing Packet" in md

def test_analytics_and_docs(tmp_path):
    convs = load_conversations(FIXTURE)
    assert role_counts(convs)["user"] == 2
    assert role_token_counts(convs)["assistant"] > 0
    assert corpus_payload(convs)["conv-1"] > 0
    trend = conversation_output_trend(convs[0])
    assert len(trend) == 3
    assert write_trend_svg([t.rolling_user for t in trend], tmp_path / "trend.svg").exists()
    md = "# Title\n\nSome words here."
    assert markdown_word_count(md) == 4
    assert heading_outline(md) == [(1, "Title")]
    glossary = render_equation_glossary([EquationEntry("Area", "A=\\pi r^2", {"A": "area"})])
    assert "Equation Glossary" in glossary
    assert write_csv(tmp_path / "rows.csv", [{"a": 1, "b": 2}]).read_text().splitlines()[0] == "a,b"
