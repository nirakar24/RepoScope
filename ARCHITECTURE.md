# RepoScope MVP Architecture

RepoScope currently implements the smallest useful codebase-aware loop:

```text
local project path
  -> source file discovery
  -> lightweight semantic chunks
  -> JSON index
  -> BM25-style retrieval
  -> optional LLM synthesis
```

## Components

- `reposcope.scanner`: walks a local directory and filters supported source files.
- `reposcope.chunker`: creates function/class chunks for Python and JS/TS, with line-window chunks for other files.
- `reposcope.indexer`: builds, saves, loads, and summarizes the JSON index.
- `reposcope.retrieval`: tokenizes query/code text and ranks chunks with BM25-style scoring plus metadata boosts.
- `reposcope.answer`: prints retrieved context or asks an LLM when `GEMINI_API_KEY` or `OPENAI_API_KEY` is available.
- `reposcope.cli`: primary interface for the MVP.
- `reposcope.api`: optional FastAPI wrapper.

## Why This Shape

The first prototype should prove retrieval quality before adding infrastructure. This version avoids Qdrant, Redis, PostgreSQL, background workers, a frontend, and auth. Those should be added only after we test against real projects and see the failure modes.

## Known Limits

- No embeddings yet, so semantic matches depend on keyword overlap.
- Regex chunking is not a full parser.
- No incremental indexing.
- No cross-repo index merging beyond pointing the index command at a parent directory.
- Optional LLM synthesis currently uses Gemini or OpenAI.

## Next Likely Upgrade

Add embeddings while keeping the same CLI:

```text
JSON lexical index + vector index
  -> retrieve by BM25 and embeddings
  -> merge results with reciprocal rank fusion
```
