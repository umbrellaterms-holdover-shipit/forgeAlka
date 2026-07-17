# Conversion Suite

This pass adds a real conversion layer instead of isolated file-shaped helpers.

## CLI

List supported direct conversions:

```bash
apex convert --list
```

Convert by suffix inference:

```bash
apex convert notes.md notes.docx
apex convert notes.docx notes.md
apex convert notes.md notes.pdf
apex convert rows.csv rows.xlsx
apex convert rows.xlsx rows.csv
apex convert deck.pptx deck.md
apex convert paper.pdf paper.txt
```

Force formats when suffixes are weird:

```bash
apex convert input.weird output.md --from docx --to md
```

Disable Pandoc preference for Markdown-to-PDF and use the pure-Python ReportLab fallback:

```bash
apex convert notes.md notes.pdf --no-pandoc
```

Emit machine-readable output:

```bash
apex convert notes.md notes.docx --json
```

## External dependency utilities

Check whether the Codespaces machine has `ffmpeg` and `pandoc`:

```bash
apex deps doctor
```

Install them via `apt-get` on Debian/Ubuntu/Codespaces:

```bash
apex deps install ffmpeg pandoc --yes
```

See what would be run without mutating the machine:

```bash
apex deps install ffmpeg pandoc --dry-run
```

## Codespaces bootstrap

On macOS/Linux:

```bash
./scripts/codespaces_bootstrap.sh
```

On Windows 11 (PowerShell):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codespaces_bootstrap.ps1
```

Or let `.devcontainer/devcontainer.json` do it during Codespaces creation.

## Implemented direct conversions

- Markdown -> DOCX via `python-docx`
- DOCX -> Markdown via `python-docx`
- Markdown -> PDF via Pandoc when available, otherwise ReportLab fallback
- PDF -> TXT/Markdown text extraction via `pypdf`
- CSV -> XLSX via `openpyxl`
- XLSX -> CSV via `openpyxl`
- PPTX -> Markdown via `python-pptx`
- Markdown -> HTML via `markdown-it-py`, with a simple fallback
- TXT <-> Markdown as text-copy conversions

## Known limits

This is a real layer now, not a magic cathedral. DOCX/PPTX/PDF extraction still cannot perfectly preserve every visual feature. Pandoc is preferred when layout fidelity matters. The pure-Python paths are intentionally practical fallbacks for a constrained dev machine.


## Generated output hygiene

Suggested ignored output folders:

```gitignore
doc_out/
docs_out/
conversion_out/
converted/
exports/
generated_outputs/
tmp_convert/
tmp_conversion/
```

Do not ignore every `*.pdf`, `*.docx`, or `*.xlsx` unless the repo will never use those as fixtures/source assets.
