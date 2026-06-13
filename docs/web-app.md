# Apex Web API and React App

This pass adds a browser skin without creating a second CLI. `apex` remains the front door; the Flask API exposes structured endpoints for the same operations, and the React app calls those endpoints.

## Install

```bash
python -m pip install -e '.[all]'
```

The `web` extra only installs Flask:

```bash
python -m pip install -e '.[web]'
```

## Run the Flask API

```bash
apex web api --host 0.0.0.0 --port 8765
```

Useful options:

```bash
apex web api --workdir .apex-web
apex web api --debug
apex web api --allow-install
```

`--allow-install` is intentionally off by default. Without it, `/api/deps/install` only allows dry-run installs. The API is a local dev server wrapper, not an auth-hardened public service.

## Run the React app

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

If the React app is not being served through Vite's proxy, set:

```bash
export VITE_APEX_API_BASE=http://localhost:8765
```

## API endpoints

### Health and discovery

```text
GET /api/health
GET /api/commands
```

### LLM and chat

```text
POST /api/llm
POST /api/chat/preflight
POST /api/chat
```

Example dry run:

```json
{
  "model": "openai/gpt-5",
  "wire_format": "auto",
  "prompt": "hello",
  "dry_run": true
}
```

The API preserves the CLI wart name: `wire_format`. Supported values:

```text
auto
openai-responses
anthropic-messages
chat-completions
```

`/api/chat/preflight` returns a list of checks before money leaves the building. The React chat panel currently uses the cost-confirmation check, and the backend check registry is built so more checks can be added later. The UI displays a real confirmation modal, not a browser alert. `/api/chat` accepts a `messages` array and returns an appended assistant message. If `conversation_id` is supplied, the updated conversation is written to disk under the API workdir. Non-streaming only for now; the CLI still has streaming support.

### Conversations

```text
GET  /api/conversations
POST /api/conversations
GET  /api/conversations/<id>
PATCH /api/conversations/<id>
DELETE /api/conversations/<id>
POST /api/conversations/<id>/messages
PATCH /api/conversations/<id>/messages/<message_id>
DELETE /api/conversations/<id>/messages/<message_id>
```

Conversations are plain JSON files written below `<workdir>/conversations`. Each saved conversation includes messages, model/wire-format metadata, timestamps, and stats such as message count, turns, words, characters, and estimated tokens. Message edits and deletes work for user and assistant messages.

### Key storage

```text
GET  /api/keys/status
POST /api/keys/status
POST /api/keys/set
```

Keys are written to files, defaulting to `~/.config/apex/openrouter.key`. The API returns metadata about the key file, never the stored secret.

### Conversion

```text
POST /api/convert
```

Multipart upload fields:

```text
file=<uploaded file>
to_format=md
from_format=optional
no_pandoc=optional true/false
```

JSON path mode:

```json
{
  "input": "notes.md",
  "output": "notes.docx",
  "from_format": "md",
  "to_format": "docx"
}
```

### Dependency helpers

```text
GET  /api/deps/doctor
POST /api/deps/doctor
POST /api/deps/install
```

Install endpoint only supports `ffmpeg` and `pandoc` by design. Non-dry-run installs require the API server to be started with `--allow-install`.

### Models and cost

```text
POST /api/models/refresh
POST /api/models/list
POST /api/models/seed
POST /api/cost
```

`/api/cost` supports either JSON paths or multipart uploads for `rates` and `requests` files.

## React panels

The React app currently has:

- Chat: GPT-like conversation view backed by `/api/chat`, with editable/deletable messages, disk persistence, model dropdown, editable temperature slider, and `/api/chat/preflight` confirmation modal before live sends.
- Conversations: list, open, delete, and inspect stats for saved disk-backed chats.
- Keys: save/check file-backed API keys without printing secrets.
- Convert: upload a file and download the converted result.
- Deps: dependency doctor and dry-run installer.
- Models: write the bundled starter catalog, refresh/list OpenRouter model snapshots, and feed the chat model dropdown.
- Cost: upload rates + request usage and estimate costs.

This is intentionally a cockpit over `apex`, not a separate architecture beast hiding in the walls.

### Cost preflight source

The chat modal estimates cost from the configured rates/model snapshot. If that file is missing, or if it exists but does not contain the selected model, the API falls back to the bundled starter catalog used by the model dropdown. The modal includes the source in the check data returned by `/api/chat/preflight`.


## Chat UX

The chat panel supports:

- model dropdown backed by a local snapshot or bundled starter catalog
- temperature slider plus editable numeric field
- optional omission of temperature from the request
- cost preflight modal before live sends
- saved conversations on disk
- user/assistant/system message editing
- message deletion
- conversation deletion
- stats for messages, turns, words, characters, and estimated tokens

Saved conversations live under:

```text
.apex-web/conversations/
```

Treat that as local state unless you explicitly want to version a fixture.
