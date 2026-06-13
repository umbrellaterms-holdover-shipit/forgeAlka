from __future__ import annotations
from pathlib import Path
import re
import textwrap
from jinja2 import Template


def render_markdown_template(template: str, **context) -> str:
    return Template(template).render(**context)


def markdown_to_pdf(markdown: str, out_path: str | Path) -> Path:
    """Render a readable Markdown-ish PDF without external binaries.

    This remains a fallback for machines without Pandoc. It now wraps text,
    gives headings distinct sizes, preserves bullets, and paginates cleanly.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ImportError("reportlab is required for markdown_to_pdf") from e
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=letter)
    _, height = letter
    margin = 72
    y = height - margin

    def new_page_if_needed(amount: int = 16) -> None:
        nonlocal y
        if y < margin + amount:
            c.showPage()
            y = height - margin

    def draw_wrapped(text: str, *, size: int = 10, leading: int = 14, indent: int = 0, bold: bool = False) -> None:
        nonlocal y
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, size)
        width = max(30, int((540 - indent) / (size * 0.55)))
        for part in textwrap.wrap(text, width=width, replace_whitespace=False) or [""]:
            new_page_if_needed(leading)
            c.drawString(margin + indent, y, part)
            y -= leading

    in_code = False
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            draw_wrapped(line, size=9, leading=12, indent=18)
            continue
        if not line.strip():
            y -= 8
            new_page_if_needed()
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            size = max(12, 22 - level * 2)
            y -= 4
            draw_wrapped(heading.group(2).strip(), size=size, leading=size + 6, bold=True)
        elif re.match(r"^[-*+]\s+", line.strip()):
            draw_wrapped("• " + re.sub(r"^[-*+]\s+", "", line.strip()), indent=12)
        elif re.match(r"^\d+[.)]\s+", line.strip()):
            draw_wrapped(line.strip(), indent=12)
        else:
            draw_wrapped(line)
    c.save()
    return out


def pdf_to_text(path: str | Path) -> str:
    """Extract text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ImportError("pypdf is required for PDF text extraction") from e
    reader = PdfReader(str(path))
    pages = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n\n<!-- page {idx} -->\n\n{text.strip()}")
    return "\n".join(pages).strip() + "\n"
