from __future__ import annotations

import os
import json
from pathlib import Path
from urllib import error, request
from textwrap import shorten

from .models import SearchResult


USER_CONFIG_DIR = Path.home() / ".config" / "repolens"
USER_CONFIG_ENV = USER_CONFIG_DIR / ".env"


def _parse_env_file(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_dotenv() -> None:
    # 1. Walk up from CWD — project-local .env takes highest priority
    for directory in [Path.cwd(), *Path.cwd().parents]:
        env_path = directory / ".env"
        if env_path.is_file():
            _parse_env_file(env_path)
            break

    # 2. User-level config — fallback for globally installed CLI
    if USER_CONFIG_ENV.is_file():
        _parse_env_file(USER_CONFIG_ENV)


_dotenv_loaded = False


def _ensure_dotenv() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        _load_dotenv()
        _dotenv_loaded = True


def build_context(results: list[SearchResult], max_chars: int = 12_000) -> str:
    parts: list[str] = []
    used = 0
    for result in results:
        chunk = result.chunk
        header = f"{chunk.path}:{chunk.start_line}-{chunk.end_line} [{chunk.kind} {chunk.name}] score={result.score:.2f}"
        body = f"{header}\n{chunk.text}"
        if used + len(body) > max_chars:
            remaining = max_chars - used
            if remaining <= 200:
                break
            body = body[:remaining]
        parts.append(body)
        used += len(body)
    return "\n\n---\n\n".join(parts)


def answer_from_results(query: str, results: list[SearchResult]) -> str:
    _ensure_dotenv()

    if not results:
        return "No relevant code chunks were found in the current index."

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        llm_answer = _try_claude_answer(query, results)
        if llm_answer:
            return llm_answer

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        llm_answer = _try_gemini_answer(query, results, gemini_key)
        if llm_answer:
            return llm_answer

    if os.getenv("OPENAI_API_KEY"):
        llm_answer = _try_openai_answer(query, results)
        if llm_answer:
            return llm_answer

    lines = [
        "Relevant code context found. No LLM answer was generated because no API key is configured.",
        "Set ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY to use LLM synthesis.",
        "",
        f"Question: {query}",
        "",
        "Top matches:",
    ]
    for index, result in enumerate(results, start=1):
        chunk = result.chunk
        preview = shorten(" ".join(chunk.text.split()), width=220, placeholder="...")
        lines.append(
            f"{index}. {chunk.path}:{chunk.start_line}-{chunk.end_line} "
            f"({chunk.kind} {chunk.name}, score {result.score:.2f})"
        )
        lines.append(f"   {preview}")
    return "\n".join(lines)


def _try_claude_answer(query: str, results: list[SearchResult]) -> str | None:
    try:
        import anthropic
    except ImportError:
        return None

    context = build_context(results)
    client = anthropic.Anthropic()
    model = os.getenv("REPOSCOPE_CLAUDE_MODEL", "claude-sonnet-4-6")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=(
                "You answer questions about a codebase using only the provided code context. "
                "Cite file paths and line ranges. If the answer is not in context, say so."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nCode context:\n{context}",
                }
            ],
        )
        return response.content[0].text if response.content else None
    except Exception as exc:
        return f"Claude request failed: {exc}"


def _try_openai_answer(query: str, results: list[SearchResult]) -> str | None:
    try:
        from openai import OpenAI
    except ImportError:
        return None

    context = build_context(results)
    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("REPOSCOPE_OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer questions about a codebase using only the provided code context. "
                    "Cite file paths and line ranges. If the answer is not in context, say so."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {query}\n\nCode context:\n{context}",
            },
        ],
    )
    return response.choices[0].message.content


def _try_gemini_answer(query: str, results: list[SearchResult], api_key: str) -> str | None:
    context = build_context(results)
    model = os.getenv("REPOSCOPE_GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You answer questions about a codebase using only the provided code context. "
                            "Cite file paths and line ranges. If the answer is not in context, say so.\n\n"
                            f"Question: {query}\n\nCode context:\n{context}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {"temperature": 0.1},
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            return (
                "Gemini request failed: quota exceeded for the configured API key. "
                "Enable billing or use a key with available Gemini quota."
            )
        return f"Gemini request failed with HTTP {exc.code}: {body[:300]}"
    except error.URLError as exc:
        return f"Gemini request failed: {exc.reason}"

    candidates = data.get("candidates") or []
    if not candidates:
        return None
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return None
    text = parts[0].get("text")
    return text if text else None
