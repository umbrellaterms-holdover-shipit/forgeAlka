# Repo apply

`apex repo apply` updates a repository from incoming files. The source can be:

- a single file
- a folder
- a zip

It matches incoming files to existing repo files, previews by default, and writes only when `--apply` is present.

## Why this exists

Sometimes the update artifact is a full package zip. Sometimes it is a handful of files. Sometimes names are mangled. Sometimes you want to overwrite one file exactly. `apex repo apply` handles those cases without needing a handcrafted `rsync` goblin every time.

## Preview first

```bash
apex repo apply incoming.zip --repo .
```

The report shows:

```text
overwritten / would overwrite
created / would create
ambiguous
no_match
backup path when applied
```

## Apply

```bash
apex repo apply incoming.zip --repo . --apply
```

## Create new files too

By default, unmatched incoming files are not created. Enable creation explicitly:

```bash
apex repo apply incoming.zip --repo . --create-missing --apply
```

Use this for package updates that add new modules.

## Single-file exact target

```bash
apex repo apply new-cli.py --repo . --target src/apexdev/cli.py --apply
```

Create the target if missing:

```bash
apex repo apply new-module.py --repo . --target src/apexdev/new_module.py --create-missing --apply
```

## Matching modes

```bash
apex repo apply SOURCE --repo . --match auto
apex repo apply SOURCE --repo . --match path
apex repo apply SOURCE --repo . --match suffix
apex repo apply SOURCE --repo . --match name
apex repo apply SOURCE --repo . --match stem
apex repo apply SOURCE --repo . --match content
apex repo apply SOURCE --repo . --match similarity
```

### `auto`

Safe default. It tries:

1. exact repo-relative path, including stripped common zip/folder roots
2. unique suffix match
3. unique filename match
4. unique stem plus extension match

Use this first.

### `path`

Only exact repo-relative path matching.

### `suffix`

Incoming path can match the end of a repo path. Useful when a zip has an extra root folder.

### `name`

Unique basename match.

### `stem`

Unique filename stem plus extension match.

### `content`

Content-based matching for identical files.

### `similarity`

Fuzzy matching. Useful when names are mangled. Dangerous enough to be explicit.

```bash
apex repo apply random-files.zip --repo . --match similarity --fuzzy-threshold 0.82
```

By default it does not match across extensions. Allow cross-extension matching only when you mean it:

```bash
apex repo apply random-files.zip --repo . --match similarity --cross-extension
```

## Backups

When applying, overwritten files are copied to a backup directory before mutation. Pick a directory explicitly:

```bash
apex repo apply incoming.zip --repo . --apply --backup-dir .apex-apply-backups/manual
```

Backup directories should be ignored by Git.

## Reports

JSON to stdout:

```bash
apex repo apply incoming.zip --repo . --json
```

JSON to file:

```bash
apex repo apply incoming.zip --repo . --out repo-apply-report.json
```

## Full lazy update command

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; ZIP="./apex_dev_tools_v0_19_docs.zip"; apex repo apply "$ZIP" --repo . --create-missing --apply; python -m pip install -e ".[all]"; if command -v npm >/dev/null 2>&1 && [ -f apps/web/package.json ]; then cd apps/web && npm install && npm run build; fi; echo "Applied."'
```

## What it does not do

`apex repo apply` does not apply unified diff patches. Use Git:

```bash
git apply --whitespace=fix update.patch
```

It also does not delete files that are absent from the incoming zip. It overwrites/creates. Deletions should be explicit so a bad zip cannot eat the repo.
