from __future__ import annotations

from pathlib import Path

from .answer import answer_from_results
from .indexer import (
    DEFAULT_INDEX_PATH,
    build_and_save_embeddings,
    build_index,
    index_stats,
    load_embeddings,
    load_index,
    save_index,
)
from .retrieval import search_chunks, search_chunks_hybrid

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, field_validator
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install API dependencies with `pip install -e .[api]`.") from exc


app = FastAPI(title="RepoScope", version="0.1.0")

_ALLOWED_INDEX_SUFFIXES = {".json"}


def _safe_path(raw: str, must_exist: bool = False) -> Path:
    from .indexer import _resolve_path
    path = _resolve_path(Path(raw)).resolve()
    if must_exist and not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {raw}")
    return path


class IndexRequest(BaseModel):
    path: str
    index_file: str = str(DEFAULT_INDEX_PATH)
    embed: bool = False

    @field_validator("index_file")
    @classmethod
    def index_file_must_be_json(cls, v: str) -> str:
        if Path(v).suffix not in _ALLOWED_INDEX_SUFFIXES:
            raise ValueError("index_file must have a .json extension")
        return v


class QueryRequest(BaseModel):
    query: str
    top_k: int = 8
    index_file: str = str(DEFAULT_INDEX_PATH)

    @field_validator("top_k")
    @classmethod
    def top_k_in_range(cls, v: int) -> int:
        if not 1 <= v <= 50:
            raise ValueError("top_k must be between 1 and 50")
        return v

    @field_validator("index_file")
    @classmethod
    def index_file_must_be_json(cls, v: str) -> str:
        if Path(v).suffix not in _ALLOWED_INDEX_SUFFIXES:
            raise ValueError("index_file must have a .json extension")
        return v


@app.post("/index")
def index_repo(request: IndexRequest) -> dict:
    repo_path = _safe_path(request.path, must_exist=True)
    if not repo_path.is_dir():
        raise HTTPException(status_code=400, detail="path must be a directory")
    index_file = Path(request.index_file)
    index = build_index(repo_path)
    save_index(index, index_file)
    if request.embed:
        build_and_save_embeddings(index, index_file)
    return index_stats(index)


def _api_search(request: QueryRequest) -> list:
    index_file = _safe_path(request.index_file)
    index = load_index(index_file)
    vector_store = load_embeddings(index_file)
    if vector_store is not None:
        from .embedder import embed_query
        query_embedding = embed_query(request.query)
        results = search_chunks_hybrid(
            index.chunks, vector_store, request.query, query_embedding, top_k=request.top_k
        )
    else:
        results = search_chunks(index.chunks, request.query, top_k=request.top_k)
    return results


@app.post("/search")
def search(request: QueryRequest) -> list[dict]:
    results = _api_search(request)
    return [
        {
            "score": result.score,
            "path": result.chunk.path,
            "start_line": result.chunk.start_line,
            "end_line": result.chunk.end_line,
            "kind": result.chunk.kind,
            "name": result.chunk.name,
            "text": result.chunk.text,
        }
        for result in results
    ]


@app.post("/ask")
def ask(request: QueryRequest) -> dict:
    results = _api_search(request)
    return {"answer": answer_from_results(request.query, results)}


@app.get("/stats")
def stats(index_file: str = str(DEFAULT_INDEX_PATH)) -> dict:
    return index_stats(load_index(_safe_path(index_file)))
