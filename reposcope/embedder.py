from __future__ import annotations

import os

import numpy as np


_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_OPENAI_EMBED_MODEL = "text-embedding-3-small"
_OPENAI_EMBED_DIM = 1536


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    model_name = os.getenv("REPOSCOPE_EMBED_MODEL", _DEFAULT_MODEL)

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        return model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
    except ImportError:
        pass

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return _openai_embed(texts, batch_size)

    raise RuntimeError(
        "No embedding provider available. Install one:\n"
        "  pip install -e \".[embed]\"   # local model, no API cost (recommended)\n"
        "  pip install -e \".[openai]\"  # uses OPENAI_API_KEY for embeddings"
    )


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


def _openai_embed(texts: list[str], batch_size: int) -> np.ndarray:
    from openai import OpenAI
    client = OpenAI()
    model = os.getenv("REPOSCOPE_EMBED_MODEL", _OPENAI_EMBED_MODEL)
    all_embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        all_embeddings.extend(item.embedding for item in response.data)
        print(f"  embedded {min(start + batch_size, len(texts))}/{len(texts)} chunks")

    return np.array(all_embeddings, dtype=np.float32)
