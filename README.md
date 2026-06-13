# Apex Dev Tools

Apex Dev Tools is a small local dev-machine toolkit for Codespaces-style work. It has one command-line front door, `apex`, plus a Flask API and React app that expose the same underlying operations.

The repo is intentionally boring at the edges: file-backed secrets, local JSON state, explicit writes, preview-before-apply repo updates, and copy/paste-able commands for the recurring terminal nonsense.

## Fast start

```bash
python -m pip install -e '.[all]'
./scripts/codespaces_bootstrap.sh
```

Set the OpenRouter key using a file, not an environment variable:

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys status openrouter
```

Run the local API and web app:

```bash
apex web api --host 0.0.0.0 --port 8765
```

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

## Repository layout

```text
src/apexdev/       Python package
apps/web/          React/Vite app
docs/              Human-facing guides and command spellbooks
tests/             Pytest suite
scripts/           Bootstrap scripts
.devcontainer/     Codespaces/devcontainer configuration
```

See [docs/repo-map.md](docs/repo-map.md) for the full map.

## Main capabilities

- `apex llm`: OpenRouter calls with file-backed API keys, wire-format selection, dry runs, model catalog support, and cost-aware preflight in the web UI.
- `apex convert`: Markdown, DOCX, PDF text extraction, CSV/XLSX, PPTX-to-Markdown, Markdown-to-HTML, and Pandoc fallbacks.
- `apex web`: Flask API plus React app for GPT-like chat, saved conversations, message editing/deletion, stats, model dropdowns, keys, conversions, dependency checks, and cost tools.
- `apex repo apply`: safely match incoming files from a file/folder/zip to existing repo files, preview changes, create missing files when requested, and back up overwritten files.
- `apex deps`: check/install system tools such as `ffmpeg` and `pandoc`.
- Corpus utilities: conversation loading, preprocessing, indexes, search, analytics, noticing packets, code-window extraction, and benchmark helpers.

## Docs index

| Guide | Use it for |
|---|---|
| [docs/repo-map.md](docs/repo-map.md) | What lives where, and what not to touch casually. |
| [docs/cli-reference.md](docs/cli-reference.md) | The `apex` command tree with examples. |
| [docs/dev-workflows.md](docs/dev-workflows.md) | Common setup/update/run/test workflows. |
| [docs/bash-spellbook.md](docs/bash-spellbook.md) | Copy/paste commands for Git, updates, zips, patches, ignores, and Codespaces nonsense. |
| [docs/openrouter-tools.md](docs/openrouter-tools.md) | Keys, models, rates, cost estimation, wire formats, and chat preflight. |
| [docs/web-app.md](docs/web-app.md) | Flask API and React app usage. |
| [docs/conversion-suite.md](docs/conversion-suite.md) | File conversion commands and limits. |
| [docs/repo-apply.md](docs/repo-apply.md) | Repo update/import/matching tool. |
| [docs/git-and-ignore.md](docs/git-and-ignore.md) | `.gitignore`, `.apex-ignore`, and ejecting ignored tracked files. |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Known failure modes and tiny antidotes. |

## Minimum useful commands

```bash
apex --help
apex convert --list
apex deps doctor
apex models list --limit 45
apex web info
apex repo apply incoming.zip --repo .
```

## Local state policy

The web app and CLI intentionally write local operational state under ignored paths:

```text
.apex-web/                 local web app state, conversations, rate snapshots
.apex-apply-backups/       repo apply backups
.apex-ignore/              user-controlled local black hole
~/.config/apex/            default API key files
```

Do not commit API keys, local conversations, generated update zips, dependency caches, or build outputs. See [docs/git-and-ignore.md](docs/git-and-ignore.md).

## Development checks

```bash
python -m pytest
python -m compileall src tests
cd apps/web && npm install && npm run build
```

For the lazy full install/update/test rhythm, use [docs/bash-spellbook.md](docs/bash-spellbook.md). The spellbook exists because flags are barnacles.
