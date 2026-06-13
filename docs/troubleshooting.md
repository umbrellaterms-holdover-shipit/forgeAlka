# Troubleshooting

Small local antidotes for common failure modes.

## `ModuleNotFoundError` immediately after applying an update

Likely cause: an update changed imports but the new module was not created. This happens when applying without `--create-missing`.

Fix by reapplying the zip with creation enabled:

```bash
apex repo apply ./update.zip --repo . --create-missing --apply
python -m pip install -e '.[all]'
```

If the CLI is broken and cannot run, extract the missing file manually from the zip:

```bash
unzip -q -o ./update.zip "src/apexdev/path/to/missing.py" -d .
python -m pip install -e '.[all]'
```

## `source must be a folder, zip file, or ordinary file`

The path you gave to `apex repo apply` does not exist from the current directory.

Check:

```bash
pwd
ls -lh ./update.zip
```

Use an absolute path when annoyed:

```bash
apex repo apply /workspaces/forgeAlka/update.zip --repo /workspaces/forgeAlka --create-missing --apply
```

## Pip says `apex` is not on PATH

Use module invocation:

```bash
python -m apexdev --help
python -m apexdev repo apply ./update.zip --repo . --create-missing --apply
```

Or run the script from the printed path.

## RVM / `set -u` unbound variable crash

If a command fails with something like:

```text
rvm_bash_nounset: unbound variable
```

remove `set -u`. Use:

```bash
bash -lc 'set -eo pipefail; cd /workspaces/forgeAlka; python -m pip install -e ".[all]"'
```

## Modal says pricing is unknown

Seed the local rates file:

```bash
mkdir -p .apex-web/rates
apex rates seed --out .apex-web/rates/openrouter.models.json
```

Then restart the API and refresh the browser. For current pricing:

```bash
apex models refresh --out .apex-web/rates/openrouter.models.json
```

## Web app cannot reach API

Start the API:

```bash
apex web api --host 0.0.0.0 --port 8765
```

Start Vite:

```bash
cd apps/web
npm run dev -- --host 0.0.0.0
```

If not using the Vite proxy, set:

```bash
export VITE_APEX_API_BASE=http://localhost:8765
```

## Dependency install endpoint refuses real installs

The API blocks real installs unless started with:

```bash
apex web api --allow-install
```

You can always install from CLI:

```bash
apex deps install ffmpeg pandoc --yes
```

## Git still tracks ignored junk

`.gitignore` is not retroactive. Eject tracked ignored files:

```bash
git ls-files -ci --exclude-standard -z | xargs -0 -r git rm --cached -r
```

Then commit.
