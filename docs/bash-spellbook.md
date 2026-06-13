# Bash spellbook

Copy/paste commands for the repeat annoyances. Most commands assume repo root is `/workspaces/forgeAlka`. Change that path when the repo lives elsewhere.

## Apply an Apex update zip and rebuild

Use when the update is a zip and the current repo already has `apex repo apply`.

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; ZIP="${1:-$(ls -1 apex_dev_tools_*.zip apex_*_v*.zip *.zip 2>/dev/null | tail -n 1)}"; echo "Applying zip: $ZIP"; apex repo apply "$ZIP" --repo . --create-missing --apply; python -m pip install -e ".[all]"; if command -v npm >/dev/null 2>&1 && [ -f apps/web/package.json ]; then cd apps/web && npm install && npm run build; fi; echo "Update applied."' -- ./apex_dev_tools_v0_19_docs.zip
```

Short form when you know the file name:

```bash
apex repo apply ./apex_dev_tools_v0_19_docs.zip --repo . --create-missing --apply
python -m pip install -e '.[all]'
cd apps/web && npm install && npm run build
```

## Preview an update zip before applying

```bash
apex repo apply ./update.zip --repo .
```

Machine-readable report:

```bash
apex repo apply ./update.zip --repo . --json --out repo-apply-report.json
```

## Apply a single file to an exact target

```bash
apex repo apply ./new-cli.py --repo . --target src/apexdev/cli.py --apply
```

Create it if the target does not exist:

```bash
apex repo apply ./new-module.py --repo . --target src/apexdev/new_module.py --create-missing --apply
```

## Apply a random folder/zip with mangled names

Try safe automatic matching first:

```bash
apex repo apply ./incoming --repo .
```

Use fuzzy matching only when safe matching fails:

```bash
apex repo apply ./incoming --repo . --match similarity --fuzzy-threshold 0.82
```

Then apply:

```bash
apex repo apply ./incoming --repo . --match similarity --fuzzy-threshold 0.82 --apply
```

## Apply a `.patch` file and rebuild

`apex repo apply` is for files/folders/zips. Unified diff patches go through Git.

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; PATCH="${1:-$(ls -1 *.patch 2>/dev/null | tail -n 1)}"; echo "Applying patch: $PATCH"; git apply --whitespace=fix "$PATCH"; python -m pip install -e ".[all]"; if command -v npm >/dev/null 2>&1 && [ -f apps/web/package.json ]; then cd apps/web && npm install && npm run build; fi; echo "Patch applied."' -- ./update.patch
```

Check before applying:

```bash
git apply --check update.patch
```

Reverse a patch that was applied but not committed:

```bash
git apply -R update.patch
```

## Rebuild/install after edits

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; python -m pip install -e ".[all]"; if command -v npm >/dev/null 2>&1 && [ -f apps/web/package.json ]; then cd apps/web && npm install && npm run build; fi; echo "Rebuilt."'
```

## Run tests and web build

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; python -m compileall src tests; python -m pytest; cd apps/web; npm install; npm run build; echo "Checks passed."'
```

## Start the API and web app

API:

```bash
cd /workspaces/forgeAlka
apex web api --host 0.0.0.0 --port 8765
```

React dev server:

```bash
cd /workspaces/forgeAlka/apps/web
npm run dev -- --host 0.0.0.0
```

## Save an OpenRouter key to the default file

```bash
printf "sk-or-REPLACE_ME" | apex keys set openrouter --stdin
apex keys status openrouter
```

Do not put the real key in a command you plan to paste into chat/logs. The `printf` form is for your terminal.

## Seed or refresh model rates

Starter catalog, no network:

```bash
mkdir -p .apex-web/rates
apex rates seed --out .apex-web/rates/openrouter.models.json
```

Live catalog, uses the key file:

```bash
apex models refresh --out .apex-web/rates/openrouter.models.json
```

List models:

```bash
apex models list --input .apex-web/rates/openrouter.models.json --limit 45
```

## Add `.apex-ignore` as a local black hole

Add this line to `.gitignore`:

```gitignore
/.apex-ignore/
```

Create it:

```bash
mkdir -p .apex-ignore
```

Move temporary junk there:

```bash
mv some-local-garbage .apex-ignore/
```

## Eject currently tracked files that are now ignored

This removes them from Git tracking only. It does not delete them from disk.

```bash
git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r
```

Add and commit everything not ignored:

```bash
git add -A
git commit -m "Apex Web v1"
```

One-shot version:

```bash
bash -lc 'set -eo pipefail; echo "Ejecting tracked files that are now ignored..."; git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r; echo "Adding everything not ignored..."; git add -A; echo "Committing..."; git commit -m "Apex Web v1"; git status --short'
```

## Useful Git sanity checks

Show untracked/modified files:

```bash
git status --short
```

Show ignored files matching a path:

```bash
git check-ignore -v .apex-web/rates/openrouter.models.json
```

Show tracked files that are ignored by current rules:

```bash
git ls-files -ci --exclude-standard
```

Show staged changes:

```bash
git diff --cached --stat
```

Undo unstaged local changes to one file:

```bash
git restore path/to/file
```

Unstage one file:

```bash
git restore --staged path/to/file
```

## Recover from `set -u`/RVM weirdness

If a long bash command dies with something like `rvm_bash_nounset: unbound variable`, do not use `set -u`. Use:

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; python -m pip install -e ".[all]"; if command -v npm >/dev/null 2>&1 && [ -f apps/web/package.json ]; then cd apps/web && npm install && npm run build; fi; echo "Done."'
```

`set -u` is useful until a shell framework has unset internal variables. Then it becomes a rake pointed at your face.

## If `apex` is installed but not on PATH

Use the module form:

```bash
python -m apexdev --help
python -m apexdev repo apply ./update.zip --repo . --create-missing --apply
```

Or inspect where pip put scripts:

```bash
python -m site --user-base
python -c 'import sysconfig; print(sysconfig.get_path("scripts"))'
```

## Remove stale local build outputs

```bash
rm -rf apps/web/dist apps/web/.vite .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
find . -type d -name __pycache__ -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -delete
```

## Safer cleanup before commit

This previews ignored files first:

```bash
git status --ignored --short
```

Then eject tracked ignored files:

```bash
git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r
```

Then commit:

```bash
git add -A
git commit -m "Apex Web v1"
```
