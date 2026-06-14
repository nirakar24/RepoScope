# RepoScope

A local-first tool for querying codebases in plain English. Point it at any repository, build an index, and ask questions — no cloud sync, no background services, no mandatory API keys.

---

## How it works

**Without `--embed` (default):**
```
repo → file discovery → chunking → JSON index → BM25 retrieval → LLM answer
```

**With `--embed` (semantic search):**
```
repo → file discovery → chunking → JSON index + .npy embeddings → BM25 + vector → RRF merge → LLM answer
```

RepoScope walks your project and breaks files into chunks — by function, class, or method boundary for Python, JS/TS, and C# (using regex-based detection), and by fixed line windows for everything else. Chunks are stored in a local JSON index and ranked with BM25 scoring at query time. If you run `index --embed`, it also generates sentence embeddings and merges the two results with Reciprocal Rank Fusion for better semantic matches.

If an LLM key is configured, `ask` feeds the top-ranked chunks to the model and returns a cited answer. If not, it falls back to showing the top matches with previews.

---

## Installation

RepoScope is not yet on PyPI. Install from source:

```bash
git clone https://github.com/nirakar24/RepoScope.git
cd RepoScope
pip install -e .
```

To add optional features:

```bash
pip install -e ".[embed]"   # semantic search (downloads ~80 MB model on first use)
pip install -e ".[claude]"  # Anthropic Claude for LLM answers
pip install -e ".[gemini]"  # Google Gemini for LLM answers
pip install -e ".[openai]"  # OpenAI for LLM answers and embeddings
pip install -e ".[api]"     # FastAPI server
pip install -e ".[all]"     # everything
```

---

## Setting up an LLM API key

`index` and `search` work with no API key. `ask` needs one to generate answers.

### Interactive setup (recommended)

```bash
repolens configure
```

Prompts for your provider and key (input is hidden), then saves to `~/.config/repolens/.env`. Picked up automatically in every session and directory from then on.

```
Which provider do you want to use for 'ask' answers?
  1) Anthropic Claude
  2) Google Gemini
  3) OpenAI

Enter 1, 2, or 3: 2

Google Gemini API key (input hidden):
Saved GEMINI_API_KEY to ~/.config/repolens/.env
```

### Environment variable

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIza..."
export OPENAI_API_KEY="sk-..."
```

### `.env` file

Create a `.env` in your project directory or any parent. RepoScope walks up from the current directory automatically:

```
GEMINI_API_KEY=AIza...
```

### Provider priority and model overrides

If multiple keys are present, the order is: **Claude → Gemini → OpenAI**.

Override the default model with environment variables:

```bash
REPOSCOPE_CLAUDE_MODEL=claude-sonnet-4-6
REPOSCOPE_GEMINI_MODEL=gemini-2.5-flash
REPOSCOPE_OPENAI_MODEL=gpt-4.1-mini
```

### Where to get keys

| Provider | Free tier | Key page |
|---|---|---|
| Google Gemini | Yes | https://aistudio.google.com/apikey |
| Anthropic Claude | No | https://console.anthropic.com |
| OpenAI | No | https://platform.openai.com/api-keys |

---

## Quick start

```bash
# Index your project
repolens index /path/to/project

# Search (instant, no LLM)
repolens search "where is authentication handled"

# Ask a question (requires an LLM key)
repolens ask "how does the database schema relate to the API routes?"
```

---

## Commands

### `configure`
Interactive first-time setup. Saves your LLM API key to `~/.config/repolens/.env`.

```bash
repolens configure
```

---

### `index`
Walks a directory, chunks its files, and writes a JSON index.

```bash
repolens index /path/to/project
```

Add `--embed` to generate sentence embeddings alongside the index. Once present, `search` and `ask` automatically switch to hybrid retrieval — no extra flag needed at query time.

```bash
repolens index /path/to/project --embed
```

Use `--index-file` (before the subcommand) to control where the index is written. Useful for keeping separate indexes per project:

```bash
repolens --index-file .reposcope/backend.json index ./backend --embed
```

The default path is `.reposcope/index.json` in the current directory.

---

### `search`
Retrieves the most relevant chunks for a query. Instant — no network call.

Uses BM25 by default. Automatically switches to hybrid BM25 + vector search if embeddings exist for the current index.

```bash
repolens search "JWT token validation"
repolens search "database migration" --top-k 5
repolens search "controller routes" --json
```

| Flag | Default | Description |
|---|---|---|
| `--top-k` | `8` | Number of results to return |
| `--json` | off | Emit results as a JSON array |

---

### `ask`
Retrieves top chunks and sends them to an LLM for a cited answer.

```bash
repolens ask "how does authentication work?"
repolens ask "what entities exist in the database?" --top-k 12
```

Falls back to listing top matches with text previews if no LLM key is set.

---

### `stats`
Prints a breakdown of the current index.

```bash
repolens stats
```

```json
{
  "files_indexed": 72,
  "chunks_indexed": 428,
  "languages": { "csharp": 160, "javascript": 25, "json": 221 },
  "kinds": { "method": 117, "block": 247, "class": 25 },
  "embeddings": ".reposcope/index.npy"
}
```

---

## Multiple projects

Use `--index-file` to maintain separate indexes. The flag goes before the subcommand.

```bash
repolens --index-file .reposcope/frontend.json index ./frontend
repolens --index-file .reposcope/backend.json  index ./backend

repolens --index-file .reposcope/frontend.json ask "how is routing configured?"
repolens --index-file .reposcope/backend.json  ask "what database tables exist?"
```

---

## Optional REST API

```bash
pip install -e ".[api]"
uvicorn reposcope.api:app --reload
```

| Method | Endpoint | Body |
|---|---|---|
| `POST` | `/index` | `{ "path": "/abs/path/to/repo", "embed": false }` |
| `POST` | `/search` | `{ "query": "...", "top_k": 8 }` |
| `POST` | `/ask` | `{ "query": "...", "top_k": 8 }` |
| `GET` | `/stats` | — |

Docs at `http://localhost:8000/docs`.

---

## Supported languages

| Language | Chunking |
|---|---|
| Python | Regex-based: splits at `def` / `async def` / `class` boundaries |
| JavaScript / TypeScript / JSX / TSX | Regex-based: splits at `function`, `class`, and arrow function boundaries |
| C# | Regex-based: splits at class, interface, record, struct, and method boundaries |
| SQL, Markdown, JSON, YAML, TOML, CSS, SCSS, HTML, Dockerfile, Makefile | Fixed 80-line windows with 15-line overlap |

Files over 750 KB and generated lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) are skipped.

---

## Ignored directories

`node_modules`, `.git`, `dist`, `build`, `bin`, `obj`, `.venv`, `__pycache__`, `.next`, `.nuxt`, `coverage`, `target`, `temp`, `vendor`, and other standard build/cache directories are excluded automatically.

---

## Roadmap

- [ ] Tree-sitter chunking for true AST-level boundaries (replacing the regex approach)
- [ ] Incremental re-indexing on file change
- [ ] Cross-repo index merging for monorepos
- [ ] Qdrant / Chroma backend for repositories with >50k chunks

---

## License

MIT
