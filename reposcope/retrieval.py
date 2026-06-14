from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

from .models import CodeChunk, SearchResult

if TYPE_CHECKING:
    import numpy as np
    from .vector_store import VectorStore


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")


def tokenize(text: str) -> list[str]:
    raw_tokens = [token.lower() for token in TOKEN_RE.findall(_split_camel(text))]
    tokens: list[str] = []
    for token in raw_tokens:
        if len(token) <= 1:
            continue
        tokens.append(token)
        tokens.extend(_token_variants(token))
    return tokens


def search_chunks(chunks: list[CodeChunk], query: str, top_k: int = 8) -> list[SearchResult]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    docs = [_document_text(chunk) for chunk in chunks]
    tokenized_docs = [tokenize(doc) for doc in docs]
    doc_freq = Counter()
    for tokens in tokenized_docs:
        doc_freq.update(set(tokens))

    avg_doc_len = sum(len(tokens) for tokens in tokenized_docs) / max(len(tokenized_docs), 1)
    scores: list[SearchResult] = []

    for chunk, tokens in zip(chunks, tokenized_docs):
        if not tokens:
            continue
        score = _bm25_score(query_tokens, tokens, doc_freq, len(tokenized_docs), avg_doc_len)
        score += _metadata_boost(chunk, query_tokens)
        if score > 0:
            scores.append(SearchResult(chunk=chunk, score=score))

    return sorted(scores, key=lambda result: result.score, reverse=True)[:top_k]


def search_chunks_hybrid(
    chunks: list[CodeChunk],
    vector_store: "VectorStore",
    query: str,
    query_embedding: "np.ndarray",
    top_k: int = 8,
    rrf_k: int = 60,
) -> list[SearchResult]:
    n = min(top_k * 3, len(chunks))

    bm25_results = search_chunks(chunks, query, top_k=n)
    bm25_rank: dict[str, int] = {r.chunk.id: rank for rank, r in enumerate(bm25_results)}

    vector_hits = vector_store.search(query_embedding, top_k=n)
    vector_rank: dict[str, int] = {chunks[i].id: rank for rank, (i, _) in enumerate(vector_hits)}

    all_ids = set(bm25_rank) | set(vector_rank)
    chunk_map = {c.id: c for c in chunks}
    rrf_scores: dict[str, float] = {}

    for chunk_id in all_ids:
        score = 0.0
        if chunk_id in bm25_rank:
            score += 1.0 / (rrf_k + bm25_rank[chunk_id])
        if chunk_id in vector_rank:
            score += 1.0 / (rrf_k + vector_rank[chunk_id])
        rrf_scores[chunk_id] = score

    ranked = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)[:top_k]
    return [SearchResult(chunk=chunk_map[cid], score=rrf_scores[cid]) for cid in ranked]


def _document_text(chunk: CodeChunk) -> str:
    return "\n".join(
        [
            chunk.path,
            chunk.language,
            chunk.kind,
            chunk.name,
            chunk.text,
        ]
    )


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_freq: Counter[str],
    doc_count: int,
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    frequencies = Counter(doc_tokens)
    doc_len = len(doc_tokens)
    score = 0.0

    for token in query_tokens:
        if token not in frequencies:
            continue
        idf = math.log(1 + (doc_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
        tf = frequencies[token]
        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += idf * (tf * (k1 + 1)) / denominator

    return score


def _metadata_boost(chunk: CodeChunk, query_tokens: list[str]) -> float:
    haystacks = {
        "name": tokenize(chunk.name),
        "path": tokenize(chunk.path),
        "kind": tokenize(chunk.kind),
        "language": tokenize(chunk.language),
    }
    score = 0.0
    for token in query_tokens:
        if token in haystacks["name"]:
            score += 2.0
        if token in haystacks["path"]:
            score += 1.0
        if token in haystacks["kind"]:
            score += 0.5
        if token in haystacks["language"]:
            score += 0.5
    return score


def _split_camel(text: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)


def _token_variants(token: str) -> list[str]:
    variants: list[str] = []
    if token.endswith("ing") and len(token) > 5:
        base = token[:-3]
        variants.append(base)
        variants.append(f"{base}e")
    if token.endswith("ed") and len(token) > 4:
        base = token[:-2]
        variants.append(base)
        variants.append(f"{base}e")
    if token.endswith("s") and len(token) > 3:
        variants.append(token[:-1])
    return variants
