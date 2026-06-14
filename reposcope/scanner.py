from __future__ import annotations

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

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORED_FILENAMES:
            continue
        if any(part in DEFAULT_IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        if detect_language(path) is None:
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
        except OSError:
            continue
        files.append(path)

    return sorted(files)
