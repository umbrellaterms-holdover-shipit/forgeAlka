# Development workflows

This guide is the boring path through common repo work. The bash spellbook has the denser copy/paste goblin commands.

## Fresh Codespaces setup

```bash
python -m pip install -e '.[all]'
./scripts/codespaces_bootstrap.sh
cd apps/web && npm install && npm run build
```

Check external tools:

```bash
apex deps doctor
```

Install missing `ffmpeg`/`pandoc`:

```bash
apex deps install ffmpeg pandoc --yes
```

## Set the OpenRouter key

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys status openrouter
```

The default key file is:

```text
~/.config/apex/openrouter.key
```

This avoids environment-variable grief and shell-history leaks.

## Seed models/rates for first-run UX

```bash
mkdir -p .apex-web/rates
apex rates seed --out .apex-web/rates/openrouter.models.json
```

Refresh live rates when you care about current pricing:

```bash
apex models refresh --out .apex-web/rates/openrouter.models.json
```

## Run the local app

Terminal 1:

```bash
apex web api --host 0.0.0.0 --port 8765
```

Terminal 2:

```bash
cd apps/web
npm run dev -- --host 0.0.0.0
```

In Codespaces, open the forwarded Vite port, usually `5173`. The API port is `8765`.

## Run checks

Python:

```bash
python -m compileall src tests
python -m pytest
```

Web:

```bash
cd apps/web
npm install
npm run build
```

## Apply an update zip

Preview:

```bash
apex repo apply ./update.zip --repo .
```

Apply with missing files and backups:

```bash
apex repo apply ./update.zip --repo . --create-missing --apply
```

Then reinstall/build:

```bash
python -m pip install -e '.[all]'
cd apps/web && npm install && npm run build
```

## Apply a unified diff patch

`apex repo apply` handles files/folders/zips, not unified diffs. Use Git for `.patch` files:

```bash
git apply --whitespace=fix update.patch
```

Then reinstall/build:

```bash
python -m pip install -e '.[all]'
cd apps/web && npm install && npm run build
```

## Commit cleanly after generated junk appears

1. Make sure `.gitignore` is updated.
2. Eject tracked files that are now ignored:

```bash
git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r
```

3. Add and commit:

```bash
git add -A
git commit -m "Apex Web v1"
```

## Local black-hole folder

Add this to `.gitignore`:

```gitignore
/.apex-ignore/
```

Then:

```bash
mkdir -p .apex-ignore
```

Everything inside `.apex-ignore/` is ignored.

## When the CLI script is not on PATH

Pip may warn that `apex` was installed somewhere not on `PATH`. You can always invoke through Python:

```bash
python -m apexdev --help
```

Or run the installed script path directly if needed:

```bash
/usr/local/python/3.12.1/bin/apex --help
```
