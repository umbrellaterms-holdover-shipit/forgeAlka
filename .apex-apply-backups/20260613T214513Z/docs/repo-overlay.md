# Repo Apply

`apex repo apply` takes one file, a folder, or a zip, matches incoming files to files in a target repository, and can overwrite or create files when explicitly told to do so.

The default is preview-only:

```bash
apex repo apply incoming.zip --repo .
```

Apply writes with backups:

```bash
apex repo apply incoming.zip --repo . --apply
```

The backup directory defaults to `.apex-apply-backups/<timestamp>/` under the repo. You can pick one explicitly:

```bash
apex repo apply incoming-folder --repo . --apply --backup-dir .apex-apply-backups/manual
```

## Matching

```bash
apex repo apply SOURCE --match auto
apex repo apply SOURCE --match path
apex repo apply SOURCE --match suffix
apex repo apply SOURCE --match name
apex repo apply SOURCE --match stem
apex repo apply SOURCE --match content
apex repo apply SOURCE --match similarity
```

`auto` tries safe matches in this order:

1. exact repo-relative path, including a stripped common zip/folder root
2. unique suffix match
3. unique file-name match
4. unique stem + extension match

`similarity` is explicit because fuzzy matching is a knife with glitter on the handle. It uses path/name similarity, requires matching extensions by default, and refuses close ties.

```bash
apex repo apply random-files.zip --repo . --match similarity --fuzzy-threshold 0.82
```

Use `--cross-extension` only when you actually want fuzzy matching to consider targets with different extensions.

## Single-file targeting

For one incoming file, you can point directly at a repo-relative target:

```bash
apex repo apply new-cli.py --repo . --target src/apexdev/cli.py --apply
```

## Creating missing files

By default, only existing repo files are write targets. Missing files are reported instead of created. To allow creating new files:

```bash
apex repo apply incoming.zip --repo . --create-missing --apply
```

For a single file with `--target`, creation uses the target path:

```bash
apex repo apply new-module.py --repo . --target src/apexdev/new_module.py --create-missing --apply
```

## Reports

```bash
apex repo apply incoming.zip --repo . --json
apex repo apply incoming.zip --repo . --out apply-report.json
```

The report includes incoming count, matched count, overwritten count, created count, ambiguous/no-match counts, target paths, match method, similarity score when relevant, and backup paths when applied.
