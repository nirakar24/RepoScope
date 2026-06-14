from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .chunker import chunk_file
from .models import CodeChunk
from .scanner import iter_source_files

if TYPE_CHECKING:
    from .vector_store import VectorStore


DEFAULT_INDEX_PATH = Path(".reposcope/index.json")


@dataclass(slots=True)
class RepoIndex:
    repo_root: str
    created_at: str
    files_indexed: int
    chunks: list[CodeChunk]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "created_at": self.created_at,
            "files_indexed": self.files_indexed,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoIndex":
        return cls(
            repo_root=data["repo_root"],
            created_at=data["created_at"],
            files_indexed=data["files_indexed"],
            chunks=[CodeChunk.from_dict(chunk) for chunk in data["chunks"]],
        )


def _resolve_path(path: Path) -> Path:
    import os
    if os.name == "nt":
        s = str(path).replace("\\", "/")
        if s.startswith("/mnt/") and len(s) > 6 and s[6] in ("", "/"):
            drive = s[5].upper()
            rest = s[6:].replace("/", "\\")
            return Path(f"{drive}:{rest}")
    return path


def build_index(repo_path: Path) -> RepoIndex:
    repo_root = _resolve_path(repo_path).resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

    source_files = iter_source_files(repo_root)
    chunks: list[CodeChunk] = []
    skipped = 0
    for source_file in source_files:
        try:
            chunks.extend(chunk_file(source_file, repo_root))
        except Exception as exc:
            print(f"warning: skipped {source_file.name}: {exc}", file=sys.stderr)
            skipped += 1

    if skipped:
        print(f"warning: {skipped} file(s) skipped due to errors", file=sys.stderr)

    return RepoIndex(
        repo_root=str(repo_root),
        created_at=datetime.now(timezone.utc).isoformat(),
        files_indexed=len(source_files) - skipped,
        chunks=chunks,
    )


def save_index(index: RepoIndex, index_path: Path = DEFAULT_INDEX_PATH) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")


def load_index(index_path: Path = DEFAULT_INDEX_PATH) -> RepoIndex:
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found: {index_path}. Run `reposcope index PATH` first.")
    return RepoIndex.from_dict(json.loads(index_path.read_text(encoding="utf-8")))


def embed_path_for(index_path: Path) -> Path:
    return index_path.parent / (index_path.stem + ".npy")


def build_and_save_embeddings(index: RepoIndex, index_path: Path) -> None:
    from .embedder import embed_texts
    from .vector_store import VectorStore

    print(f"Generating embeddings for {len(index.chunks)} chunks...")
    texts = [
        f"{chunk.kind} {chunk.name} in {chunk.path}\n{chunk.text}"
        for chunk in index.chunks
    ]
    embeddings = embed_texts(texts)
    store = VectorStore(embeddings)
    npy_path = embed_path_for(index_path)
    store.save(npy_path)
    print(f"Embeddings saved to {npy_path}  (shape {embeddings.shape})")


def load_embeddings(index_path: Path) -> "VectorStore | None":
    from pathlib import Path as _Path
    npy_path = embed_path_for(index_path)
    if not npy_path.exists():
        return None
    try:
        from .vector_store import VectorStore
        return VectorStore.load(npy_path)
    except Exception as exc:
        print(f"warning: could not load embeddings from {npy_path}: {exc}", file=sys.stderr)
        return None


def index_stats(index: RepoIndex) -> dict[str, Any]:
    language_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for chunk in index.chunks:
        language_counts[chunk.language] = language_counts.get(chunk.language, 0) + 1
        kind_counts[chunk.kind] = kind_counts.get(chunk.kind, 0) + 1

    return {
        "repo_root": index.repo_root,
        "created_at": index.created_at,
        "files_indexed": index.files_indexed,
        "chunks_indexed": len(index.chunks),
        "languages": dict(sorted(language_counts.items())),
        "kinds": dict(sorted(kind_counts.items())),
    }
