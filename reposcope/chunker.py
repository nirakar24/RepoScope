from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import CodeChunk
from .scanner import detect_language


PY_SYMBOL_RE = re.compile(r"^(?P<indent>\s*)(?P<kind>def|async\s+def|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
JS_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:(?P<kind>class|function)\s+(?P<name>[A-Za-z_$][\w$]*)|"
    r"(?:const|let|var)\s+(?P<var>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>)",
    re.MULTILINE,
)
C_SHARP_SYMBOL_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*"
    r"(?:(?:public|private|protected|internal|static|sealed|abstract|async|partial|virtual|override|readonly|required)\s+)*"
    r"(?:(?P<typekind>class|interface|record|struct|enum)\s+(?P<type>[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?P<return>[A-Za-z_][A-Za-z0-9_<>,\[\]?\.]*)\s+(?P<method>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:where\s+[^{]+)?\{?)",
    re.MULTILINE,
)

_LINE_WINDOW_OVERLAP = 15


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except UnicodeDecodeError:
            return None
    except OSError:
        return None


def chunk_file(path: Path, repo_root: Path, max_lines: int = 80) -> list[CodeChunk]:
    text = read_text(path)
    if text is None or not text.strip():
        return []

    language = detect_language(path) or "text"
    relative_path = path.resolve().relative_to(repo_root.resolve()).as_posix()

    if language == "python":
        chunks = _symbol_chunks(text, relative_path, repo_root, language, PY_SYMBOL_RE)
    elif language in {"javascript", "typescript"}:
        chunks = _symbol_chunks(text, relative_path, repo_root, language, JS_SYMBOL_RE)
    elif language == "csharp":
        chunks = _csharp_chunks(text, relative_path, repo_root)
    else:
        chunks = []

    if chunks:
        return chunks

    return _line_window_chunks(text, relative_path, repo_root, language, max_lines=max_lines)


def _symbol_chunks(
    text: str,
    relative_path: str,
    repo_root: Path,
    language: str,
    pattern: re.Pattern[str],
) -> list[CodeChunk]:
    lines = text.splitlines()
    matches = list(pattern.finditer(text))
    chunks: list[CodeChunk] = []

    for index, match in enumerate(matches):
        start_line = text.count("\n", 0, match.start()) + 1
        end_line = text.count("\n", 0, matches[index + 1].start()) if index + 1 < len(matches) else len(lines)
        chunk_text = "\n".join(lines[start_line - 1 : end_line]).strip()
        if not chunk_text:
            continue

        kind = (match.groupdict().get("kind") or "function").replace("async def", "function")
        if kind == "def":
            kind = "function"
        name = match.groupdict().get("name") or match.groupdict().get("var") or "anonymous"
        chunks.append(
            CodeChunk(
                id=_chunk_id(relative_path, start_line, end_line, name),
                repo_root=str(repo_root.resolve()),
                path=relative_path,
                language=language,
                kind=kind,
                name=name,
                start_line=start_line,
                end_line=end_line,
                text=chunk_text,
            )
        )

    return chunks


def _csharp_chunks(text: str, relative_path: str, repo_root: Path) -> list[CodeChunk]:
    lines = text.splitlines()
    matches = list(C_SHARP_SYMBOL_RE.finditer(text))
    chunks: list[CodeChunk] = []

    for index, match in enumerate(matches):
        start_line = text.count("\n", 0, match.start()) + 1
        end_line = text.count("\n", 0, matches[index + 1].start()) if index + 1 < len(matches) else len(lines)
        chunk_text = "\n".join(lines[start_line - 1 : end_line]).strip()
        if not chunk_text:
            continue

        typekind = match.groupdict().get("typekind")
        if typekind:
            kind = typekind
            name = match.groupdict().get("type") or "anonymous"
        else:
            kind = "method"
            name = match.groupdict().get("method") or "anonymous"

        chunks.append(
            CodeChunk(
                id=_chunk_id(relative_path, start_line, end_line, name),
                repo_root=str(repo_root.resolve()),
                path=relative_path,
                language="csharp",
                kind=kind,
                name=name,
                start_line=start_line,
                end_line=end_line,
                text=chunk_text,
            )
        )

    return chunks


def _line_window_chunks(
    text: str,
    relative_path: str,
    repo_root: Path,
    language: str,
    max_lines: int,
) -> list[CodeChunk]:
    lines = text.splitlines()
    chunks: list[CodeChunk] = []
    step = max(1, max_lines - _LINE_WINDOW_OVERLAP)

    for start in range(0, len(lines), step):
        end = min(start + max_lines, len(lines))
        chunk_text = "\n".join(lines[start:end]).strip()
        if not chunk_text:
            continue
        start_line = start + 1
        end_line = end
        chunks.append(
            CodeChunk(
                id=_chunk_id(relative_path, start_line, end_line, "block"),
                repo_root=str(repo_root.resolve()),
                path=relative_path,
                language=language,
                kind="block",
                name="block",
                start_line=start_line,
                end_line=end_line,
                text=chunk_text,
            )
        )

    return chunks


def _chunk_id(path: str, start_line: int, end_line: int, name: str) -> str:
    raw = f"{path}:{start_line}:{end_line}:{name}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
