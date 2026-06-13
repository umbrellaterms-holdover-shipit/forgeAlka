from pathlib import Path
import py_compile

from apexdev.media.flux_catalogs import OCCUPATIONS, OUTFITS, LOCATIONS, PROPS, SAMPLE_PROMPTS, default_catalog
from apexdev.media.prompt_dataset import generate_default_grid
from apexdev.indexes.schemas import REQUIRED_INDEX_FAMILIES, schema_names, SCHEMA_EXAMPLES
from apexdev.rules.blocked_affordance_assets import ACTIONS, PROPS as BA_PROPS, atoms_by_tag
from apexdev.rules.template_engine import Atom, Slot, Literal, Template, RenderContext, traverse
from apexdev.reference_assets.validation import compile_embedded_source


def test_embedded_noticing_v2_source_compiles():
    import apexdev.reference_assets.noticing_engine_v2 as src
    path = Path(src.__file__)
    assert path.exists()
    assert compile_embedded_source(path)


def test_default_flux_catalogs_are_present():
    assert len(OCCUPATIONS) >= 40
    assert len(OUTFITS) >= 30
    assert len(LOCATIONS) >= 30
    assert len(PROPS) >= 30
    assert SAMPLE_PROMPTS and SAMPLE_PROMPTS[0].startswith("A ")
    grid = generate_default_grid(limit=3)
    assert len(grid) == 3
    assert grid[0].id


def test_index_schema_examples_are_available():
    assert "base" in REQUIRED_INDEX_FAMILIES
    assert "term_dict.jsonl" in schema_names()
    assert SCHEMA_EXAMPLES


def test_blocked_affordance_assets_and_template_engine():
    assert len(ACTIONS) >= 5
    assert len(BA_PROPS) >= 5
    assert atoms_by_tag("anger")["actions"]
    template = Template([
        Slot("Action", [Atom("reach", 1, {"controlled"}), Atom("shove", 1, {"anger"})]),
        Literal("for"),
        Slot("Prop", [Atom("hand", 1, {"neutral"}), Atom("bloody fingers", 2, {"injured"})]),
    ])
    result = traverse(template, RenderContext(desired_tags={"anger"}, forbidden_tags={"injured"}))
    assert "shove" in result.text
    assert "bloody" not in result.text
