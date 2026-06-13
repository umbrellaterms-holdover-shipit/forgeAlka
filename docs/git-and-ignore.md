# Git and ignore rules

This repo produces local junk on purpose: web state, conversation JSON, model-rate snapshots, update zips, backups, Python caches, and web build output. Git should not eat that stuff unless you explicitly decide it is source.

## Root local black hole

Add this to `.gitignore`:

```gitignore
/.apex-ignore/
```

Then create it:

```bash
mkdir -p .apex-ignore
```

Anything in `.apex-ignore/` is ignored completely.

## Apex-specific ignore tail

Add this near the bottom of `.gitignore`:

```gitignore
# Apex local state
.apex-web/
.apex-apply-backups/
.apex-overlays/
.apex-cache/
.apex-tmp/
.apex-runs/
.apex-logs/
/.apex-ignore/

# Local secrets
*.env
.env
.env.*
!.env.example
*.key
*.secret
secrets/
.local-secrets/

# Generated model/rate snapshots
rates/openrouter.models.json
rates/*.local.json
rates/*.snapshot.json

# Generated update bundles
apex_dev_tools_*.zip
apex_dev_tools_*.patch
apex_*_v*.zip
apex_*_v*.patch

# Repo apply reports and rejects
repo-apply-report*.json
*.apply-report.json
*.orig
*.rej

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
.coverage.*
htmlcov/
build/
dist/
*.egg-info/
.venv/
venv/

# Node/Vite
node_modules/
apps/web/dist/
apps/web/.vite/
apps/web/coverage/
npm-debug.log*

# Conversion output folders
doc_out/
docs_out/
conversion_out/
converted/
exports/
generated_outputs/
tmp_convert/
tmp_conversion/

# LaTeX scratch
*.aux
*.bbl
*.bcf
*.blg
*.fdb_latexmk
*.fls
*.lof
*.lot
*.run.xml
*.synctex.gz
*.toc
*.xdv
```

Do not blanket-ignore `*.zip`, `*.patch`, `*.pdf`, `*.docx`, or `*.xlsx` unless you are certain this repo will never need fixtures or source assets with those extensions.

## Eject ignored files already tracked

Changing `.gitignore` does not automatically remove already tracked files. Use:

```bash
git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r
```

Then commit:

```bash
git add -A
git commit -m "Apex Web v1"
```

## Inspect ignore behavior

Why is a file ignored?

```bash
git check-ignore -v path/to/file
```

Which tracked files are currently ignored?

```bash
git ls-files -ci --exclude-standard
```

Show ignored files in status:

```bash
git status --ignored --short
```

## Keep a tracked empty folder

Git does not track empty folders. If you want a folder to exist but ignore its contents:

```gitignore
/some-folder/*
!/some-folder/.gitkeep
```

Then:

```bash
mkdir -p some-folder
touch some-folder/.gitkeep
git add some-folder/.gitkeep
```

For `.apex-ignore`, usually do not track the folder. It is better as a pure local black hole.
