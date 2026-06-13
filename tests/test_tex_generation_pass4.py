from pathlib import Path
import json

from apexdev.documents.tex_tools import (
    EquationAtlas,
    EquationBlock,
    Section,
    StructuralBlock,
    SymbolEntry,
    render_equation_atlas,
    summarize_tex_atlas,
)
from apexdev.cli import main


def _sample_atlas() -> EquationAtlas:
    return EquationAtlas(
        title="Generic Equation Atlas",
        subtitle="Validation Fixture",
        symbols=[SymbolEntry(r"$x$", "x", "Input value")],
        sections=[
            Section(
                "Computable Relations",
                intro="Small fixture for renderer and validator coverage.",
                equations=[
                    EquationBlock(
                        "Double an input.",
                        "Input value $x$.",
                        "Output value $y$.",
                        "Arithmetic over real numbers.",
                        r"y=2x",
                        "y equals two x",
                        "This is an ordinary computable relation.",
                    ),
                    EquationBlock(
                        "Add one.",
                        "Input value $x$.",
                        "Output value $z$.",
                        "Arithmetic over real numbers.",
                        r"z=x+1",
                        "z equals x plus one",
                        "This is another computable relation.",
                    ),
                ],
                structures=[
                    StructuralBlock(
                        "State transition notation.",
                        "State A and state B.",
                        "Updated state A and updated state B.",
                        "A transition procedure P exists.",
                        r"(A,B)\xrightarrow{P}(A',B')",
                        "Structural notation, not a computable equation.",
                    )
                ],
            )
        ],
    )


def test_tex_renderer_outputs_numbered_equation_blocks():
    tex = render_equation_atlas(_sample_atlas())
    summary = summarize_tex_atlas(tex)
    assert "\\newcounter{eqblock}[section]" in tex
    assert "\\Needspace{18\\baselineskip}" in tex
    assert summary["equation_blocks"] == 2
    assert summary["structural_blocks"] == 1
    assert summary["has_numbered_eqblock_counter"]
    assert summary["has_needspace_section_guard"]


def test_tex_validation_catches_structural_equation():
    atlas = EquationAtlas(
        title="Bad",
        sections=[
            Section(
                "Bad Section",
                equations=[
                    EquationBlock(
                        "gesture",
                        "states",
                        "states",
                        "none",
                        r"(A,B)\xrightarrow{P}(A',B')",
                        "A B arrow P A prime B prime",
                        "not computable",
                    )
                ],
            )
        ],
    )
    tex = render_equation_atlas(atlas)
    summary = summarize_tex_atlas(tex)
    assert summary["validation_warnings"]


def test_cli_tex_validate(tmp_path):
    tex_path = tmp_path / "atlas.tex"
    tex_path.write_text(render_equation_atlas(_sample_atlas()), encoding="utf-8")

    validate = tmp_path / "validate.json"
    main(["tex-validate", "--input", str(tex_path), "--out", str(validate)])
    data = json.loads(validate.read_text())
    assert data["equation_blocks"] == 2
    assert data["structural_blocks"] == 1
