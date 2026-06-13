from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Any
import re

from jinja2 import Environment, BaseLoader


def escape_tex(text: str) -> str:
    """Escape TeX-special characters in prose fields.

    This function is intentionally for prose, not math. Math content should be
    passed through as trusted LaTeX.
    """
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(text))


@dataclass(slots=True)
class SymbolEntry:
    symbol: str
    read_as: str
    meaning: str


@dataclass(slots=True)
class AcronymEntry:
    acronym: str
    expansion: str
    read_as: str
    meaning: str


@dataclass(slots=True)
class EquationBlock:
    """A computable equation block.

    The equation appears before pronunciation and meaning, matching the user
    correction from the equation-atlas TeX generation work.
    """

    for_: str
    inputs: str
    outputs: str
    assumptions: str
    equation: str
    pronunciation: str
    meaning: str
    label: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuralBlock:
    """Quarantined structural notation.

    These blocks are not counted as computable equations. They exist only when
    nearby computable equations expand the implied operations.
    """

    for_: str
    inputs_named: str
    outputs_named: str
    hidden_assumptions: str
    notation: str
    meaning: str


@dataclass(slots=True)
class Section:
    title: str
    intro: str = ""
    equations: list[EquationBlock] = field(default_factory=list)
    structures: list[StructuralBlock] = field(default_factory=list)


@dataclass(slots=True)
class EquationAtlas:
    title: str
    subtitle: str = ""
    document_rules: str = ""
    symbols: list[SymbolEntry] = field(default_factory=list)
    acronyms: list[AcronymEntry] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)


ATLAS_TEMPLATE = r"""
\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{mathrsfs}
\usepackage{longtable,booktabs,array}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{needspace}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.65em}
\setlist[itemize]{leftmargin=1.5em,itemsep=0.15em,topsep=0.15em}
\titleformat{\section}{\Large\bfseries}{\thesection}{0.6em}{}
\titleformat{\subsection}{\large\bfseries}{\thesubsection}{0.6em}{}

% Keep section headers from hanging at the bottom of a page.
\let\oldsection\section
\renewcommand{\section}{\Needspace{18\baselineskip}\oldsection}

% Equation blocks are numbered by section: [section.index].
\newcounter{eqblock}[section]
\renewcommand{\theeqblock}{\thesection.\arabic{eqblock}}

\newcommand{\EqBlock}[7]{%
\par\Needspace{16\baselineskip}%
\refstepcounter{eqblock}%
\noindent\begin{minipage}{\linewidth}
\vspace{0.45em}\hrule\vspace{0.45em}
\textbf{Equation [\theeqblock]}\\
\textbf{For:} #1\\
\textbf{Inputs:} #2\\
\textbf{Outputs:} #3\\
\textbf{Assumptions:} #4
\[
#5
\]
\textbf{Pronunciation:} ``#6''\\
\textbf{Meaning:} #7
\vspace{0.45em}
\end{minipage}\par\vspace{0.35em}%
}

\newcommand{\StructBlock}[6]{%
\par\Needspace{12\baselineskip}%
\noindent\begin{minipage}{\linewidth}
\vspace{0.45em}\hrule\vspace{0.45em}
\textbf{Structural notation, not a computable equation.}\\
\textbf{For:} #1\\
\textbf{Inputs named:} #2\\
\textbf{Outputs named:} #3\\
\textbf{Assumptions hidden by notation:} #4
\[
#5
\]
\textbf{What this notation means:} #6\\
\textbf{Computability rule:} this block is allowed only because nearby equation blocks expand the implied operations into channel observations, memory updates, distances, probabilities, or energy terms.
\vspace{0.45em}
\end{minipage}\par\vspace{0.35em}%
}

\title{ << atlas.title|tex >><% if atlas.subtitle %>\\\large << atlas.subtitle|tex >><% endif %> }
\author{}
\date{}

\begin{document}
\maketitle

\tableofcontents
\newpage

\section*{Document Rules}
\addcontentsline{toc}{section}{Document Rules}
<< atlas.document_rules|tex >>

<% if atlas.symbols %>
\section{Absolute Symbol Registry}
\begin{longtable}{>{\raggedright\arraybackslash}p{0.18\linewidth} >{\raggedright\arraybackslash}p{0.28\linewidth} >{\raggedright\arraybackslash}p{0.44\linewidth}}
\toprule
Symbol & Read as & Intended meaning \\
\midrule
<% for s in atlas.symbols -%>
<< s.symbol >> & << s.read_as|tex >> & << s.meaning|tex >> \\
<% endfor -%>
\bottomrule
\end{longtable}
<% endif %>

<% if atlas.acronyms %>
\section{Acronym and Abbreviation Registry}
\begin{longtable}{>{\raggedright\arraybackslash}p{0.14\linewidth} >{\raggedright\arraybackslash}p{0.28\linewidth} >{\raggedright\arraybackslash}p{0.18\linewidth} >{\raggedright\arraybackslash}p{0.32\linewidth}}
\toprule
Acronym & Expansion & Read as & Meaning \\
\midrule
<% for a in atlas.acronyms -%>
<< a.acronym|tex >> & << a.expansion|tex >> & << a.read_as|tex >> & << a.meaning|tex >> \\
<% endfor -%>
\bottomrule
\end{longtable}
<% endif %>

<% for section in atlas.sections %>
\section{ << section.title|tex >> }
<% if section.intro %><< section.intro|tex >><% endif %>

<% for e in section.equations %>
\EqBlock
{ << e.for_|tex >> }
{ << e.inputs|tex >> }
{ << e.outputs|tex >> }
{ << e.assumptions|tex >> }
{ << e.equation >> }
{ << e.pronunciation|tex >> }
{ << e.meaning|tex >> }
<% endfor %>

<% for s in section.structures %>
\StructBlock
{ << s.for_|tex >> }
{ << s.inputs_named|tex >> }
{ << s.outputs_named|tex >> }
{ << s.hidden_assumptions|tex >> }
{ << s.notation >> }
{ << s.meaning|tex >> }
<% endfor %>
<% endfor %>

\end{document}
"""


def _environment() -> Environment:
    env = Environment(loader=BaseLoader(), autoescape=False, trim_blocks=True, lstrip_blocks=True, variable_start_string="<<", variable_end_string=">>", block_start_string="<%", block_end_string="%>", comment_start_string="<#", comment_end_string="#>")
    env.filters["tex"] = escape_tex
    return env


def render_equation_atlas(atlas: EquationAtlas) -> str:
    """Render an EquationAtlas to TeX using Jinja, not giant f-strings."""
    return _environment().from_string(ATLAS_TEMPLATE).render(atlas=atlas)


def write_equation_atlas(atlas: EquationAtlas, path: str | Path) -> Path:
    out = Path(path)
    out.write_text(render_equation_atlas(atlas), encoding="utf-8")
    return out


def render_tex_document(title: str, sections: list[tuple[str, str]]) -> str:
    """Compatibility wrapper for old callers.

    Uses the Jinja-backed atlas renderer rather than direct string assembly.
    """
    atlas = EquationAtlas(
        title=title,
        document_rules="Basic TeX document generated from section prose.",
        sections=[
            Section(title=heading, intro=body)
            for heading, body in sections
        ],
    )
    return render_equation_atlas(atlas)


def _parse_macro_blocks(tex: str, macro_name: str) -> list[list[str]]:
    """Parse simple top-level TeX macro calls such as \\EqBlock{...}{...}.

    This is not a full TeX parser, but it handles nested braces well enough for
    the generated atlas macros.
    """
    pattern = "\\" + macro_name
    out: list[list[str]] = []
    i = 0
    while True:
        start = tex.find(pattern, i)
        if start == -1:
            break
        j = start + len(pattern)
        args: list[str] = []
        while j < len(tex):
            while j < len(tex) and tex[j].isspace():
                j += 1
            if j >= len(tex) or tex[j] != "{":
                break
            depth = 0
            arg_start = j + 1
            while j < len(tex):
                ch = tex[j]
                if ch == "{" and (j == 0 or tex[j - 1] != "\\"):
                    depth += 1
                elif ch == "}" and (j == 0 or tex[j - 1] != "\\"):
                    depth -= 1
                    if depth == 0:
                        args.append(tex[arg_start:j].strip())
                        j += 1
                        break
                j += 1
            # macros here have fixed arg count; continue while braces follow
            if macro_name == "EqBlock" and len(args) == 7:
                break
            if macro_name == "StructBlock" and len(args) == 6:
                break
        if args:
            out.append(args)
        i = max(j, start + len(pattern))
    return out


def parse_eqblocks(tex: str) -> list[EquationBlock]:
    rows = []
    for args in _parse_macro_blocks(tex, "EqBlock"):
        if len(args) >= 7:
            rows.append(EquationBlock(args[0], args[1], args[2], args[3], args[4], args[5], args[6]))
    return rows


def parse_structblocks(tex: str) -> list[StructuralBlock]:
    rows = []
    for args in _parse_macro_blocks(tex, "StructBlock"):
        if len(args) >= 6:
            rows.append(StructuralBlock(args[0], args[1], args[2], args[3], args[4], args[5]))
    return rows


NONCOMPUTABLE_PATTERNS = [
    r"\\xrightarrow",
    r"\\mapsto",
    r"\\Longrightarrow",
    r"\\Rightarrow",
    r"\\leftrightarrow",
]


def validate_computable_equation_blocks(blocks: list[EquationBlock]) -> list[str]:
    """Return validation warnings for equation blocks that look structural.

    This captures a common equation-atlas failure mode: protocol
    arrows and diagrammatic signatures should be StructuralBlock, not EqBlock.
    """
    warnings: list[str] = []
    for i, block in enumerate(blocks, 1):
        for pattern in NONCOMPUTABLE_PATTERNS:
            if re.search(pattern, block.equation):
                warnings.append(f"EqBlock {i} appears structural/noncomputable: pattern {pattern}")
        if not block.inputs.strip() or not block.outputs.strip():
            warnings.append(f"EqBlock {i} lacks explicit inputs or outputs")
        if not any(op in block.equation for op in ["=", "\\le", "\\ge", "\\approx", "\\sum", "\\int", "\\frac"]):
            warnings.append(f"EqBlock {i} may not compute or constrain a quantity")
    return warnings


def summarize_tex_atlas(tex: str) -> dict[str, Any]:
    eqs = parse_eqblocks(tex)
    structs = parse_structblocks(tex)
    return {
        "equation_blocks": len(eqs),
        "structural_blocks": len(structs),
        "sections": len(re.findall(r"\\section\\{", tex)),
        "has_numbered_eqblock_counter": "\\newcounter{eqblock}[section]" in tex,
        "has_needspace_section_guard": "\\Needspace{18\\baselineskip}" in tex,
        "validation_warnings": validate_computable_equation_blocks(eqs),
    }
