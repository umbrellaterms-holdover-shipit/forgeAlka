from pathlib import Path
import json, wave
from apexdev.media.prompt_dataset import compose_prompt, expand_grid
from apexdev.media.audio_chatter import ChatterFragment, generate_schedule, render_tts_script, write_placeholder_wav
from apexdev.rules.components import Component
from apexdev.rules.rule_engine import RuleEngine
from apexdev.rules.renderers import render_xml
from apexdev.knots.generator import generate_knot
from apexdev.core.loader import load_conversations
from apexdev.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_conversation.json"

def test_flux_chatter_rules_knots(tmp_path):
    prompt = compose_prompt({"style": "portrait", "person": "archivist", "outfit": "coat", "pose": "standing", "location": "library", "prop": "lamp", "lighting": "soft light"}, salt="x")
    assert prompt.id and "archivist" in prompt.prompt
    assert len(expand_grid({"style": ["portrait"], "person": ["a"], "outfit": ["b"], "pose": ["c"], "location": ["d"], "prop": ["e"], "lighting": ["f"]})) == 1
    schedule = generate_schedule([ChatterFragment("hello world", "a"), ChatterFragment("second line", "b")], seed=2)
    assert schedule[0].start_s == 0 and "a:" in render_tts_script(schedule)
    wav = write_placeholder_wav(schedule, tmp_path / "out.wav")
    with wave.open(str(wav), "rb") as wf:
        assert wf.getnframes() > 0
    root = Component("dialogue", "root").add(Component("utterance", "root.1", "I can't do that"))
    engine = RuleEngine()
    engine.add_rule("defrule blocked\nwhen kind == utterance\nwhen text contains \"can't\"\nthen flag blocked_affordance")
    assert engine.evaluate(root)[0].rule == "blocked"
    assert "<dialogue" in render_xml(root)
    assert generate_knot(load_conversations(FIXTURE)[0], seed=0).question.endswith("?")

def test_cli(tmp_path):
    extracted = tmp_path / "snips.json"
    main(["extract", "--input", str(FIXTURE), "--out", str(extracted)])
    assert json.loads(extracted.read_text())
    index = tmp_path / "index.json"
    main(["index", "--input", str(FIXTURE), "--out", str(index)])
    assert "spines" in json.loads(index.read_text())
    packet = tmp_path / "packet.md"
    main(["noticing-packet", "--input", str(FIXTURE), "--out", str(packet)])
    assert "Noticing Packet" in packet.read_text()
    out = tmp_path / "analytics"
    main(["analytics", "--input", str(FIXTURE), "--out", str(out)])
    assert (out / "summary.json").exists()
    fragments = tmp_path / "frags.txt"
    fragments.write_text("hello world\nsecond line\n")
    chatter = tmp_path / "chatter"
    main(["chatter", "--fragments", str(fragments), "--out", str(chatter)])
    assert (chatter / "tts_script.txt").exists()
