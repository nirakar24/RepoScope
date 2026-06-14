from __future__ import annotations

from pathlib import Path

import numpy as np


class VectorStore:
    def __init__(self, embeddings: np.ndarray) -> None:
        arr = embeddings.astype(np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        self._embeddings = arr / np.maximum(norms, 1e-10)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        q = query_embedding.astype(np.float32)
        norm = np.linalg.norm(q)
        q = q / max(float(norm), 1e-10)
        scores = self._embeddings @ q
        k = min(top_k, len(scores))
        top_indices = np.argpartition(scores, -k)[-k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return [(int(i), float(scores[i])) for i in top_indices]

    def save(self, path: Path) -> None:
        np.save(path, self._embeddings)

    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        embeddings = np.load(path)
        instance = cls.__new__(cls)
        instance._embeddings = embeddings.astype(np.float32)
        return instance

    def __len__(self) -> int:
        return len(self._embeddings)
