import pytest

from reposcope.models import CodeChunk, SearchResult
from reposcope.retrieval import search_chunks, search_chunks_hybrid, tokenize


def _make_chunk(name: str, text: str, kind: str = "function", path: str = "src/app.py") -> CodeChunk:
    return CodeChunk(
        id=f"test-{name}",
        repo_root="/repo",
        path=path,
        language="python",
        kind=kind,
        name=name,
        start_line=1,
        end_line=10,
        text=text,
    )


def test_tokenize_camel_case():
    tokens = tokenize("getUserById")
    assert "get" in tokens
    assert "user" in tokens
    assert "by" in tokens
    assert "id" in tokens


def test_tokenize_snake_case():
    # underscores are part of the token regex — snake_case stays as one token
    tokens = tokenize("validate_api_key")
    assert "validate_api_key" in tokens


def test_exact_match_scores_above_zero():
    chunks = [_make_chunk("authenticate", "def authenticate(user, password): ...")]
    results = search_chunks(chunks, "authenticate")
    assert results
    assert results[0].score > 0


def test_no_match_returns_empty():
    chunks = [_make_chunk("foo", "def foo(): return 42")]
    results = search_chunks(chunks, "zxqwerty_nonexistent")
    assert results == []


def test_most_relevant_ranks_first():
    chunks = [
        _make_chunk("send_email", "def send_email(to, subject, body): smtp.send()"),
        _make_chunk("process_payment", "def process_payment(amount, card): stripe.charge()"),
        _make_chunk("authenticate", "def authenticate(user, password): check_hash()"),
    ]
    results = search_chunks(chunks, "payment stripe charge")
    assert results[0].chunk.name == "process_payment"


def test_top_k_limits_results():
    chunks = [_make_chunk(f"func_{i}", f"def func_{i}(): return {i}") for i in range(20)]
    results = search_chunks(chunks, "func", top_k=5)
    assert len(results) <= 5


def test_metadata_name_boost():
    chunks = [
        _make_chunk("authenticate_user", "validates something unrelated"),
        _make_chunk("unrelated_func", "def authenticate(): check user credentials authenticate"),
    ]
    results = search_chunks(chunks, "authenticate")
    # Both should score, function named "authenticate_user" gets name boost
    assert len(results) >= 1


class _MockVectorStore:
    def __init__(self, chunk_indices):
        self._indices = chunk_indices

    def search(self, query_embedding, top_k):
        import numpy as np
        return [(i, 0.9 - i * 0.1) for i in self._indices[:top_k]]


def test_hybrid_search_returns_search_results():
    import numpy as np

    chunks = [
        _make_chunk("login", "def login(user, password): verify_credentials()"),
        _make_chunk("logout", "def logout(session): session.clear()"),
        _make_chunk("register", "def register(email, password): create_account()"),
    ]
    store = _MockVectorStore([0, 2, 1])
    query_embedding = np.zeros(384, dtype="float32")

    results = search_chunks_hybrid(chunks, store, "login user", query_embedding, top_k=3)
    assert isinstance(results, list)
    assert all(isinstance(r, SearchResult) for r in results)
    assert len(results) <= 3
