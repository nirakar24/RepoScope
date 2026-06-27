from __future__ import annotations

import os
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".txt": "text",
    ".cs": "csharp",
    ".csproj": "xml",
    ".sql": "sql",
}

SUPPORTED_FILENAMES = {
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    ".env.example": "env",
    ".gitignore": "gitignore",
}

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".reposcope",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "bin",
    "obj",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    "temp",
    "vendor",
}

IGNORED_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "project.assets.json",
}


def detect_language(path: Path) -> str | None:
    if path.name in SUPPORTED_FILENAMES:
        return SUPPORTED_FILENAMES[path.name]
    return SUPPORTED_EXTENSIONS.get(path.suffix.lower())


def iter_source_files(root: Path, max_file_bytes: int = 750_000) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []

    # os.walk with in-place pruning of dirnames so we never descend into
    # ignored directories. rglob would still stat every file inside them
    # (e.g. a bundled venv's site-packages — tens of thousands of files),
    # which is prohibitively slow on networked / mounted filesystems.
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
        for filename in filenames:
            if filename in IGNORED_FILENAMES:
                continue
            path = Path(dirpath) / filename
            if detect_language(path) is None:
                continue
            try:
                if path.stat().st_size > max_file_bytes:
                    continue
            except OSError:
                continue
            files.append(path)

    return sorted(files)
