# Repository map

This repo has one job: be a local dev-machine toolbox with a single command surface, `apex`, plus a web skin over the same operations.

## Top-level layout

```text
src/apexdev/       Python package
apps/web/          React/Vite browser app
docs/              User/developer guides
tests/             Pytest suite
scripts/           Bootstrap and maintenance scripts
.devcontainer/     Codespaces configuration
pyproject.toml     Python package metadata and dependencies
README.md          Landing page and docs index
```

## Python package layout

```text
src/apexdev/cli.py                 argparse CLI entrypoint for `apex`
src/apexdev/config.py              file-backed secret paths and helpers
src/apexdev/system_tools.py        ffmpeg/pandoc doctor + apt install helpers
src/apexdev/web_api.py             Flask app and HTTP endpoints
src/apexdev/repo_overlay.py        implementation behind `apex repo apply`
```

The module name `repo_overlay.py` is historical/internal. The public command is `apex repo apply`.

### LLM/OpenRouter

```text
src/apexdev/llm/openrouter.py      OpenRouter HTTP client and payload shaping
src/apexdev/llm/costs.py           offline cost estimation from rate snapshots
src/apexdev/llm/rates.py           starter/example model catalog writers
src/apexdev/llm/model_catalog.py   model snapshot loading and dropdown rows
src/apexdev/llm/preflight.py       registry for checks before live chat sends
```

The happy path is file-backed keys:

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
```

The web chat calls preflight before sending live requests. Cost confirmation is one registered check, not hard-coded into the submit button.

### Documents/conversion

```text
src/apexdev/documents/conversion.py        format registry and conversion dispatcher
src/apexdev/documents/pandoc_tools.py      Pandoc bridge
src/apexdev/documents/docx_tools.py        DOCX read/write helpers
src/apexdev/documents/pdf_tools.py         PDF generation/extraction helpers
src/apexdev/documents/spreadsheet_tools.py CSV/XLSX helpers
src/apexdev/documents/slides_tools.py      PPTX-to-Markdown helpers
src/apexdev/documents/tex_tools.py         generic TeX atlas validation/summaries
```

These are generic utilities. Project-specific document names do not belong here.

### Web app

```text
apps/web/src/main.jsx              React app entrypoint and UI components
apps/web/src/styles.css            app styling
apps/web/package.json              npm scripts/dependencies
apps/web/vite.config.js            dev proxy and Vite config
```

The app exposes chat, conversations, model/rate management, key setup, conversion, dependency checks, and cost estimation. It is not a separate product. It is a skin over `apex`/Flask operations.

### Local web state

```text
.apex-web/conversations/           saved conversation JSON files
.apex-web/rates/                   local model/rate snapshots
```

These are local and should be ignored by Git.

### Corpus/index/search utilities

```text
src/apexdev/core/                  conversation models, loader, normalization
src/apexdev/conversations/         preprocessing, splitting, active path helpers
src/apexdev/preprocessing/         dedupe, normalization, code windows
src/apexdev/indexes/               inverted index, postings, spines, anchors
src/apexdev/search/                search adapters and query/index helpers
src/apexdev/analytics/             role metrics, output trends, lexical summaries
src/apexdev/noticing/              noticing packet generation and benchmark helpers
src/apexdev/rules/                 rule/template/render/validation helpers
src/apexdev/knots/                 question/knot generation helper
src/apexdev/media/                 small image/audio/prompt helper modules
```

These are still small utility modules. Treat them as a toolbox, not as a framework cathedral.

## Tests

```text
tests/test_openrouter_tools.py       keys/models/cost/preflight helpers
tests/test_web_api.py                Flask endpoints when Flask is available
tests/test_repo_overlay.py           repo apply matching behavior
tests/test_conversion_suite.py       conversion dispatcher and direct formats
```

Run everything:

```bash
python -m pytest
```

## What should stay out of Git

```text
.apex-web/
.apex-apply-backups/
.apex-ignore/
node_modules/
apps/web/dist/
*.egg-info/
__pycache__/
*.pyc
apex_dev_tools_*.zip
apex_dev_tools_*.patch
```

See [git-and-ignore.md](git-and-ignore.md) for the full local-ignore recipe.
