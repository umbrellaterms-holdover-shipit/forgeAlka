from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class EquationEntry:
    name: str
    latex: str
    variables: dict[str, str]
    notes: str = ""

def render_equation_glossary(entries: list[EquationEntry]) -> str:
    lines = ["# Equation Glossary", ""]
    for e in entries:
        lines += [f"## {e.name}", "", f"```tex\n{e.latex}\n```"]
        if e.variables:
            lines += ["", "| Symbol | Meaning |", "| --- | --- |"]
            for sym, meaning in e.variables.items():
                lines.append(f"| `{sym}` | {meaning} |")
        if e.notes:
            lines += ["", e.notes]
        lines.append("")
    return "\n".join(lines)

def render_equation_tex(entries: list[EquationEntry], title: str = "Equation Glossary") -> str:
    from .tex_tools import render_tex_document
    sections = []
    for e in entries:
        vars_text = "\n".join(f"{k}: {v}" for k, v in e.variables.items())
        sections.append((e.name, f"\\[\n{e.latex}\n\\]\n\n{vars_text}\n\n{e.notes}"))
    return render_tex_document(title, sections)
