from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class CodeChunk:
    id: str
    repo_root: str
    path: str
    language: str
    kind: str
    name: str
    start_line: int
    end_line: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeChunk":
        return cls(**data)


@dataclass(slots=True)
class SearchResult:
    chunk: CodeChunk
    score: float

