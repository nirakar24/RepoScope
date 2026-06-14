# RepoScope

A local-first, codebase-aware AI tool. Point it at any repository, and ask questions about the code in plain English.

No cloud indexing. No background services. No mandatory API keys. Your code stays on your machine.

---

## How it works

```
your repo → file discovery → symbol-aware chunking → JSON index → BM25 retrieval → LLM answer
```

RepoScope walks your project, breaks files into logical chunks (by function, class, or method), stores them in a local JSON index, and ranks them with BM25 scoring when you search. If you configure an LLM key, it synthesises a cited answer from the top matches.

---

## Installation

Requires Python 3.11 or later. After installing, `reposcope --help` should work immediately — no further setup required.

### Recommended: pipx (isolated environment, command available globally)

```bash
pipx install reposcope
```

### With uv

```bash
uv tool install reposcope
```

### With pip

```bash
pip install reposcope
```

### Add-ons

Install extras for the features you want:

```bash
pip install "reposcope[embed]"   # semantic search (sentence-transformers, ~80 MB model)
pip install "reposcope[claude]"  # Anthropic Claude for LLM answers
pip install "reposcope[gemini]"  # Google Gemini for LLM answers
pip install "reposcope[openai]"  # OpenAI for LLM answers and embeddings
pip install "reposcope[all]"     # everything
```

### From source

```bash
git clone https://github.com/nirakar24/reposcope.git
cd reposcope
pip install -e .
```

---

## Setting up an LLM API key

`search` and `index` work with no API key. The `ask` command needs one to generate answers.

### The easy way — interactive setup

```bash
reposcope configure
```

This prompts you to choose a provider, paste your key (input is hidden), and saves it to `~/.config/reposcope/.env`. It's picked up automatically from then on, in any directory.

```
RepoScope — LLM configuration

Which provider do you want to use for 'ask' answers?
  1) Anthropic Claude
  2) Google Gemini
  3) OpenAI

Enter 1, 2, or 3: 2

Google Gemini API key (input hidden):
Saved GEMINI_API_KEY to ~/.config/reposcope/.env
```

### Manually — environment variable

Set the key in your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) and it will be available in every session:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # Claude (recommended)
export GEMINI_API_KEY="AIza..."         # Gemini
export OPENAI_API_KEY="sk-..."          # OpenAI
```

### Manually — `.env` file

Create a `.env` file in your project directory or any parent directory. RepoScope walks up from the current directory automatically:

```bash
# .env
GEMINI_API_KEY=AIza...
```

### Priority order

If multiple keys are present, RepoScope tries them in this order: **Claude → Gemini → OpenAI**.

### Where to get keys

| Provider | Link | Free tier |
|---|---|---|
| Anthropic Claude | https://console.anthropic.com | No (pay-as-you-go) |
| Google Gemini | https://aistudio.google.com/apikey | Yes |
| OpenAI | https://platform.openai.com/api-keys | No (pay-as-you-go) |

---

## Quick start

```bash
# 1. Index your project
reposcope index /path/to/your/project

# 2. Search it (instant, no LLM needed)
reposcope search "where is authentication handled"

# 3. Ask a question (requires an LLM key — see Configuration)
reposcope ask "how does the database schema relate to the API routes?"
```

---

## Commands

### `index`
Scans a directory and writes a local JSON index.

```bash
reposcope index /path/to/project
```

Add `--embed` to also generate semantic embeddings alongside the index (requires the `[embed]` extra). Search and ask commands detect the `.npy` file automatically and switch to hybrid retrieval — no extra flags needed at query time.

```bash
reposcope index /path/to/project --embed
```

By default the index is saved to `.reposcope/index.json` in your current directory. Use `--index-file` to choose a different path — useful when you maintain indexes for multiple projects.

```bash
reposcope --index-file .reposcope/myproject.json index /path/to/project --embed
```

---

### `search`
Ranks chunks against your query using BM25. Instant. No network call.

```bash
reposcope search "JWT token validation"
reposcope search "database migration" --top-k 5
reposcope search "controller routes" --json   # machine-readable output
```

| Flag | Default | Description |
|---|---|---|
| `--top-k` | `8` | Number of results to return |
| `--json` | off | Emit results as a JSON array |

---

### `ask`
Retrieves the top matching chunks and sends them to an LLM for a cited answer.

```bash
reposcope ask "how does authentication work?"
reposcope ask "what entities exist in the database?" --top-k 12
```

Falls back to showing top matches with previews if no LLM key is configured.

---

### `stats`
Prints a breakdown of the current index.

```bash
reposcope stats
```

```json
{
  "files_indexed": 72,
  "chunks_indexed": 428,
  "languages": { "csharp": 160, "javascript": 25, "json": 221 },
  "kinds": { "method": 117, "block": 247, "class": 25 }
}
```

---

## Configuration

Create a `.env` file anywhere in your project tree (or in the directory you run `reposcope` from). RepoScope reads it automatically on the first `ask` command.

```bash
# .env

# Pick one (or more — Claude is tried first, then Gemini, then OpenAI)
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# Optional: override the default model for each provider
REPOSCOPE_CLAUDE_MODEL=claude-sonnet-4-6
REPOSCOPE_GEMINI_MODEL=gemini-2.5-flash
REPOSCOPE_OPENAI_MODEL=gpt-4.1-mini
```

`search` and `index` never make network calls regardless of whether a key is set.

---

## Managing multiple projects

Use `--index-file` to keep a separate index per project. The flag goes before the subcommand.

```bash
reposcope --index-file .reposcope/frontend.json index ./frontend
reposcope --index-file .reposcope/backend.json  index ./backend

reposcope --index-file .reposcope/frontend.json ask "how is routing configured?"
reposcope --index-file .reposcope/backend.json  ask "what database tables exist?"
```

---

## Optional REST API

Install the API extra and start the server:

```bash
pip install -e ".[api]"
uvicorn reposcope.api:app --reload
```

| Method | Endpoint | Body |
|---|---|---|
| `POST` | `/index` | `{ "path": "/abs/path/to/repo" }` |
| `POST` | `/search` | `{ "query": "...", "top_k": 8 }` |
| `POST` | `/ask` | `{ "query": "...", "top_k": 8 }` |
| `GET` | `/stats` | — |

Interactive docs are at `http://localhost:8000/docs`.

---

## Supported languages

| Language | Chunking strategy |
|---|---|
| Python | Functions and classes (regex AST) |
| JavaScript / TypeScript / JSX / TSX | Functions, classes, arrow functions |
| C# | Classes, interfaces, records, methods |
| SQL, Markdown, JSON, YAML, TOML, CSS, SCSS, HTML | Line-window with 15-line overlap |
| Dockerfile, Makefile, `.gitignore` | Line-window |

Files larger than 750 KB and generated lock files (`package-lock.json`, `yarn.lock`, etc.) are skipped automatically.

---

## What gets ignored

`node_modules`, `.git`, `dist`, `build`, `bin`, `obj`, `.venv`, `__pycache__`, `.next`, `.nuxt`, `coverage`, and other standard build/cache directories are excluded by default.

---

## Roadmap

- [ ] Tree-sitter chunking for precise AST boundaries
- [ ] Incremental re-indexing on file change
- [ ] Cross-repo index merging for monorepos
- [ ] Qdrant / Chroma backend for large repositories (>50k chunks)

---

## License

MIT
