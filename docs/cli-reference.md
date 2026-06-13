# `apex` CLI reference

`apex` is the single public command. The CLI is intentionally grouped by task so API quirks do not become top-level verbs.

## Help

```bash
apex --help
apex convert --help
apex llm --help
apex repo apply --help
```

## LLM/OpenRouter

### Store/check key

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys status openrouter
apex keys path openrouter
```

Override the default key file for one command:

```bash
apex llm --model openai/gpt-5 --prompt "hello" --api-key-file ./secrets/openrouter.key
```

### Send or inspect a request

Dry run first:

```bash
apex llm --model openai/gpt-5 --prompt "hello" --dry-run
```

Live request:

```bash
apex llm --model openai/gpt-5 --prompt "hello"
```

Use an input message file:

```bash
apex llm --model anthropic/claude-sonnet-4 --messages messages.json --out reply.md
```

Set temperature and output limit:

```bash
apex llm --model openai/gpt-5 --prompt "summarize this" --temperature 0.2 --max-tokens 800
```

Force compatibility plumbing only when needed:

```bash
apex llm --model openai/gpt-5 --prompt "hello" --wire-format openai-responses
apex llm --model anthropic/claude-sonnet-4 --prompt "hello" --wire-format anthropic-messages
apex llm --model meta-llama/some-model --prompt "hello" --wire-format chat-completions
```

`--wire-format auto` chooses by model slug:

```text
openai/*      -> openai-responses
anthropic/*   -> anthropic-messages
everything else -> chat-completions
```

## Models/rates/costs

Seed a starter catalog:

```bash
apex rates seed --out rates/openrouter.models.json
```

Refresh live OpenRouter model data:

```bash
apex models refresh --out rates/openrouter.models.json
```

List models for a dropdown or quick terminal browse:

```bash
apex models list --input rates/openrouter.models.json --limit 45
apex models list --limit 45
apex models list --limit 45 --json
```

Estimate costs from request usage records:

```bash
apex cost --rates rates/openrouter.models.json --requests requests.jsonl
apex cost --rates rates/openrouter.models.json --requests requests.jsonl --json
```

Request record shape:

```json
{"model":"provider/model","usage":{"prompt_tokens":1000,"completion_tokens":500}}
```

## File conversion

List supported conversions:

```bash
apex convert --list
```

Common conversions:

```bash
apex convert notes.md notes.docx
apex convert notes.docx notes.md
apex convert notes.md notes.pdf
apex convert paper.pdf paper.txt
apex convert paper.pdf paper.md
apex convert rows.csv rows.xlsx
apex convert rows.xlsx rows.csv
apex convert deck.pptx deck.md
apex convert notes.md notes.html
```

Force weird suffixes:

```bash
apex convert input.blob output.md --from docx --to md
```

Avoid Pandoc and use fallback paths:

```bash
apex convert notes.md notes.pdf --no-pandoc
```

## External dependencies

Check:

```bash
apex deps doctor
apex deps doctor ffmpeg pandoc
```

Dry-run install:

```bash
apex deps install ffmpeg pandoc --dry-run
```

Install on Debian/Ubuntu/Codespaces:

```bash
apex deps install ffmpeg pandoc --yes
```

## Web API/UI

Print run instructions:

```bash
apex web info
```

Run API:

```bash
apex web api --host 0.0.0.0 --port 8765
```

Use a different state folder:

```bash
apex web api --workdir .apex-web-dev
```

Allow the API to perform real dependency installs. Keep this off unless you mean it:

```bash
apex web api --allow-install
```

## Repo file application

Preview incoming file matching:

```bash
apex repo apply incoming.zip --repo .
```

Apply and back up overwritten files:

```bash
apex repo apply incoming.zip --repo . --apply
```

Create missing files too:

```bash
apex repo apply incoming.zip --repo . --create-missing --apply
```

Apply one file to one explicit path:

```bash
apex repo apply new-cli.py --repo . --target src/apexdev/cli.py --apply
```

Write JSON report:

```bash
apex repo apply incoming.zip --repo . --out repo-apply-report.json
```

Fuzzy matching. Use this only when names/paths are mangled:

```bash
apex repo apply random-files.zip --repo . --match similarity --fuzzy-threshold 0.82
```

## Corpus/search/analytics helpers

These operate on conversation/export-like JSON inputs accepted by the loader.

```bash
apex extract --input conversations.json --out snippets.json
apex index --input conversations.json --out index.json
apex search --input conversations.json --query "pricing preflight" --out results.json
apex analytics --input conversations.json --out analytics/
apex noticing-packet --input conversations.json --out packet.md
apex preprocess --input conversations.json --out preprocessed.json
apex code-windows --input conversations.json --out code-windows.json
apex sentences --input conversations.json --out sentences.tsv
apex chunks --input conversations.json --out chunks.jsonl
```

## Misc helpers

```bash
apex doc-export --input notes.md --out doc_out --pdf
apex tex-validate --input equations.tex --out tex-summary.json
apex chatter --fragments fragments.txt --out chatter/
apex benchmark --input evidence.json --out benchmark.md --expected-term pricing
```
