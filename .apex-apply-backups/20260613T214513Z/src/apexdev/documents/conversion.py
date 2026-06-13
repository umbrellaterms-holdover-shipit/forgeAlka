from __future__ import annotations

"""Unified file-conversion registry.

The goal of this module is to stop hiding converters behind isolated helper
names. It provides one public `convert_file` entry point and a compact list of
supported direct conversions. When Pandoc is installed, it can be used as a
fallback for document pairs Pandoc understands.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable
import html
import json
import shutil

from .docx_tools import docx_to_markdown, markdown_to_docx
from .pdf_tools import markdown_to_pdf, pdf_to_text
from .spreadsheet_tools import csv_to_xlsx, xlsx_to_csv
from .slides_tools import pptx_to_markdown
from .pandoc_tools import has_pandoc, pandoc_convert

TEXT_EXTENSIONS = {".md": "md", ".markdown": "md", ".txt": "txt", ".text": "txt"}
FORMAT_BY_SUFFIX = {
    **TEXT_EXTENSIONS,
    ".docx": "docx",
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".tex": "tex",
    ".json": "json",
}


@dataclass(frozen=True)
class ConversionResult:
    input_path: str
    output_path: str
    input_format: str
    output_format: str
    method: str
    warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


Converter = Callable[[Path, Path], ConversionResult]


def normalize_format(fmt: str | None) -> str | None:
    if fmt is None:
        return None
    fmt = fmt.lower().strip().lstrip(".")
    aliases = {"markdown": "md", "text": "txt", "xlsm": "xlsx", "powerpoint": "pptx", "word": "docx"}
    return aliases.get(fmt, fmt)


def detect_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    try:
        return FORMAT_BY_SUFFIX[suffix]
    except KeyError as e:
        raise ValueError(f"Cannot infer file format from suffix {suffix!r}. Pass --from/--to explicitly.") from e


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _md_to_docx(src: Path, dst: Path) -> ConversionResult:
    markdown_to_docx(_read_text(src), dst)
    return ConversionResult(str(src), str(dst), "md", "docx", "python-docx", [])


def _docx_to_md(src: Path, dst: Path) -> ConversionResult:
    _write_text(dst, docx_to_markdown(src))
    return ConversionResult(str(src), str(dst), "docx", "md", "python-docx", [])


def _md_to_pdf(src: Path, dst: Path) -> ConversionResult:
    markdown_to_pdf(_read_text(src), dst)
    return ConversionResult(str(src), str(dst), "md", "pdf", "reportlab-fallback", [])


def _pdf_to_txt(src: Path, dst: Path) -> ConversionResult:
    _write_text(dst, pdf_to_text(src))
    return ConversionResult(str(src), str(dst), "pdf", "txt", "pypdf", [])


def _pdf_to_md(src: Path, dst: Path) -> ConversionResult:
    text = pdf_to_text(src)
    _write_text(dst, text)
    return ConversionResult(str(src), str(dst), "pdf", "md", "pypdf-text", ["PDF layout, images, and tables are not preserved."])


def _csv_to_xlsx(src: Path, dst: Path) -> ConversionResult:
    csv_to_xlsx(src, dst)
    return ConversionResult(str(src), str(dst), "csv", "xlsx", "openpyxl", [])


def _xlsx_to_csv(src: Path, dst: Path) -> ConversionResult:
    xlsx_to_csv(src, dst)
    return ConversionResult(str(src), str(dst), "xlsx", "csv", "openpyxl", ["Only the first worksheet is exported unless --sheet is added in a future pass."])


def _pptx_to_md(src: Path, dst: Path) -> ConversionResult:
    _write_text(dst, pptx_to_markdown(src))
    return ConversionResult(str(src), str(dst), "pptx", "md", "python-pptx", [])


def _md_to_html(src: Path, dst: Path) -> ConversionResult:
    text = _read_text(src)
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        body = "\n".join(f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip())
        warnings = ["markdown-it-py not installed; emitted simple escaped paragraphs."]
    else:
        body = MarkdownIt().render(text)
        warnings = []
    _write_text(dst, "<!doctype html>\n<html><body>\n" + body + "\n</body></html>\n")
    return ConversionResult(str(src), str(dst), "md", "html", "markdown-it-py", warnings)


def _txt_to_md(src: Path, dst: Path) -> ConversionResult:
    _write_text(dst, _read_text(src))
    return ConversionResult(str(src), str(dst), "txt", "md", "text-copy", [])


def _md_to_txt(src: Path, dst: Path) -> ConversionResult:
    _write_text(dst, _read_text(src))
    return ConversionResult(str(src), str(dst), "md", "txt", "text-copy", ["Markdown syntax is preserved as literal text."])


DIRECT_CONVERTERS: dict[tuple[str, str], Converter] = {
    ("md", "docx"): _md_to_docx,
    ("docx", "md"): _docx_to_md,
    ("md", "pdf"): _md_to_pdf,
    ("pdf", "txt"): _pdf_to_txt,
    ("pdf", "md"): _pdf_to_md,
    ("csv", "xlsx"): _csv_to_xlsx,
    ("xlsx", "csv"): _xlsx_to_csv,
    ("pptx", "md"): _pptx_to_md,
    ("md", "html"): _md_to_html,
    ("txt", "md"): _txt_to_md,
    ("md", "txt"): _md_to_txt,
}

PANDOC_FORMATS = {"md", "markdown", "docx", "html", "pdf", "tex", "txt"}


def available_conversions() -> list[dict[str, str]]:
    rows = [
        {"from": a, "to": b, "method": getattr(fn, "__name__", "direct").lstrip("_")}
        for (a, b), fn in sorted(DIRECT_CONVERTERS.items())
    ]
    rows.append({"from": "pandoc-supported", "to": "pandoc-supported", "method": "pandoc fallback when installed"})
    return rows


def render_available_conversions() -> str:
    lines = ["# Available conversions", ""]
    for row in available_conversions():
        lines.append(f"- {row['from']} -> {row['to']} ({row['method']})")
    return "\n".join(lines)


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    from_format: str | None = None,
    to_format: str | None = None,
    prefer_pandoc: bool = True,
) -> ConversionResult:
    src = Path(input_path)
    dst = Path(output_path)
    if not src.exists():
        raise FileNotFoundError(src)
    src_fmt = normalize_format(from_format) or detect_format(src)
    dst_fmt = normalize_format(to_format) or detect_format(dst)
    if src_fmt == dst_fmt:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return ConversionResult(str(src), str(dst), src_fmt, dst_fmt, "copy", ["Input and output formats match; file copied."])
    if prefer_pandoc and has_pandoc() and (src_fmt, dst_fmt) == ("md", "pdf"):
        try:
            pandoc_convert(src, dst, from_format="markdown", to_format="pdf")
            return ConversionResult(str(src), str(dst), src_fmt, dst_fmt, "pandoc", [])
        except Exception as exc:
            # Let the direct ReportLab fallback run. The resulting file is less
            # pretty, but successful conversion beats ornamental failure.
            direct_result = _md_to_pdf(src, dst)
            return ConversionResult(direct_result.input_path, direct_result.output_path, src_fmt, dst_fmt, direct_result.method, [f"pandoc failed; fell back to reportlab: {exc}"])
    direct = DIRECT_CONVERTERS.get((src_fmt, dst_fmt))
    if direct:
        dst.parent.mkdir(parents=True, exist_ok=True)
        return direct(src, dst)
    if prefer_pandoc and has_pandoc() and src_fmt in PANDOC_FORMATS and dst_fmt in PANDOC_FORMATS:
        pandoc_convert(src, dst, from_format=("markdown" if src_fmt == "md" else src_fmt), to_format=("markdown" if dst_fmt == "md" else dst_fmt))
        return ConversionResult(str(src), str(dst), src_fmt, dst_fmt, "pandoc", [])
    raise ValueError(f"No converter registered for {src_fmt} -> {dst_fmt}. Use `apex convert --list` to see supported direct conversions.")


def write_conversion_result(path: str | Path, result: ConversionResult) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return out
