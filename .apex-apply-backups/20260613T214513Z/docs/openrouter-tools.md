# OpenRouter tools

`apex` has one CLI surface. LLM calls use one command:

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys status openrouter
apex llm --model openai/gpt-5 --prompt "Say hello"
apex llm --model anthropic/claude-sonnet-4 --messages messages.json --out reply.md
apex llm --model mistralai/some-model --prompt "Use the broad fallback" --wire-format chat-completions
apex rates seed --out rates/openrouter.models.json
apex models refresh --out rates/openrouter.models.json
apex models list --input rates/openrouter.models.json --limit 45
apex cost --rates rates/openrouter.models.json --requests requests.jsonl --json
```

Dry-run a request without touching the network:

```bash
apex llm --model example/model --prompt "hello" --dry-run
```


## File-backed API key

The normal key path is a local file, not an environment variable:

```bash
printf "sk-or-..." | apex keys set openrouter --stdin
apex keys path openrouter
apex keys status openrouter
```

The default path is `~/.config/apex/openrouter.key`. The writer tries to set
mode `0600`. You can override the path for a one-off run:

```bash
apex llm --model openai/gpt-5 --prompt "hello" --api-key-file ./secrets/openrouter.key
```

`--api-key` still exists for tests and one-off debugging, but it is deliberately
not the happy path because shell history is where secrets go to become raccoons.

## Wire format

The provider/API split is exposed as a flag because it is compatibility plumbing,
not a different user action. Use `--wire-format` when the automatic choice is
wrong or when you need to inspect an exact payload shape.

```bash
apex llm --model openai/gpt-5 --prompt "hello" --wire-format openai-responses
apex llm --model anthropic/claude-sonnet-4 --prompt "hello" --wire-format anthropic-messages
apex llm --model meta-llama/some-model --prompt "hello" --wire-format chat-completions
```

Available values:

- `auto`: chooses based on the model slug.
- `openai-responses`: `/api/v1/responses`, OpenAI/Responses-shaped payloads.
- `anthropic-messages`: `/api/v1/messages`, Anthropic/Messages-shaped payloads.
- `chat-completions`: `/api/v1/chat/completions`, broad compatibility fallback.

Current `auto` policy:

- `openai/*` -> `openai-responses`
- `anthropic/*` -> `anthropic-messages`
- everything else -> `chat-completions`

Use `--dry-run` to print the selected wire format, endpoint, and payload before
spending money.


## Chat preflight

The web chat calls `/api/chat/preflight` before a live send. The first registered
check estimates input tokens and cost from a local model snapshot, then asks for
confirmation before `/api/chat` is called. The check system is registry-based in
`apexdev.llm.preflight`, so future checks can be added without rewriting the
React submit path.

For a useful first run, write the bundled starter catalog. For billing-sensitive work, refresh from OpenRouter:

```bash
apex rates seed --out .apex-web/rates/openrouter.models.json
apex models refresh --out .apex-web/rates/openrouter.models.json
```

The token estimate is local and deliberately approximate. Real invoices still
come from the provider response.

Request records for `apex cost` can be JSON or JSONL:

```json
{"model":"provider/model","usage":{"prompt_tokens":1000,"completion_tokens":500}}
```

The calculator expects OpenRouter-style pricing fields such as `prompt`,
`completion`, `request`, `image`, `web_search`, `internal_reasoning`,
`input_cache_read`, and `input_cache_write`. Values are interpreted as USD per
unit/token, matching the model API shape.

Use a fresh local snapshot for real cost estimates:

```bash
apex models refresh --out rates/openrouter.models.json
```


## Starter model catalog

The package includes a bundled starter catalog with 45+ OpenRouter options so the web chat model dropdown is useful before the first network refresh. The catalog uses the same `data[].pricing.prompt` / `data[].pricing.completion` shape as `/api/v1/models`, with prices stored as USD per token. It is a bootstrap convenience, not a final invoice authority.

```bash
apex rates seed --out rates/openrouter.models.json
apex models list --limit 45
```

The React chat panel reads the local snapshot path and falls back to the bundled catalog when the file is missing. The Models panel can also write the starter catalog or refresh from OpenRouter.
