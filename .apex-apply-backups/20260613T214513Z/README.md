# Apex Dev Tools

A small Python toolkit for a Codespaces-based dev machine. The single CLI is `apex`.

## Repository layout

```text
src/apexdev/      Python package
apps/web/         React web app
docs/             Human-facing guides
tests/            Pytest suite
scripts/          Bootstrap and maintenance scripts
.devcontainer/    Codespaces/devcontainer configuration
```

## What is in here

- Unified file conversion: Markdown, DOCX, PDF text, CSV/XLSX, PPTX to Markdown, and Pandoc fallbacks.
- Dependency helpers for Codespaces/Linux: `ffmpeg` and `pandoc` checks/installs.
- OpenRouter LLM, file-backed API key, bundled starter model catalog, live model snapshots, chat preflight, and offline cost-estimation utilities.
- Flask API + React app for disk-backed chat, message editing/deletion, conversation management, key setup, conversion, deps, models, and cost estimation.
- Conversation preprocessing, indexing, search, analytics, noticing packets, and rule/knot utilities.
- Generic TeX equation-atlas rendering and validation helpers.

## Install

```bash
python -m pip install -e '.[all]'
```

For Codespaces:

```bash
./scripts/codespaces_bootstrap.sh
```

## CLI

```bash
apex --help
apex convert --list
apex deps doctor
apex deps install ffmpeg pandoc --yes
```

OpenRouter:

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys status openrouter
apex llm --model openai/gpt-5 --prompt "Hello"
apex llm --model example/model --prompt "Hello" --dry-run --wire-format chat-completions
apex rates seed --out rates/openrouter.models.json      # bundled starter catalog, 45+ options
apex models refresh --out rates/openrouter.models.json   # live OpenRouter snapshot
apex models list --input rates/openrouter.models.json --limit 45
apex cost --rates rates/openrouter.models.json --requests requests.jsonl --json
```

Repo apply / import patching:

```bash
apex repo apply incoming.zip --repo .          # preview matches
apex repo apply incoming-folder --repo . --apply
apex repo apply new-cli.py --repo . --target src/apexdev/cli.py --apply
```

Web UI/API:

```bash
apex web api --host 0.0.0.0 --port 8765
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

Conversation and corpus utilities:

```bash
apex extract --input fixture.json --out snippets.json
apex index --input fixture.json --out index.json
apex noticing-packet --input fixture.json --out packet.md
apex analytics --input fixture.json --out analytics/
apex chatter --fragments fragments.txt --out chatter/
apex benchmark --input fixture.json --out benchmark.md
apex tex-validate --input equations.tex --out tex-summary.json
```

See `docs/conversion-suite.md`, `docs/openrouter-tools.md`, `docs/web-app.md`, and `docs/repo-overlay.md` for details.
