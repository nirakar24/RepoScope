from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .answer import answer_from_results
from .indexer import (
    DEFAULT_INDEX_PATH,
    build_and_save_embeddings,
    build_index,
    index_stats,
    load_embeddings,
    load_index,
    save_index,
)
from .retrieval import search_chunks, search_chunks_hybrid


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="reposcope",
        description="Index and query a local codebase.",
    )
    parser.add_argument(
        "--index-file",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Path to the RepoScope JSON index.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build an index for a local repository.")
    index_parser.add_argument("path", type=Path, help="Repository or project directory to index.")
    index_parser.add_argument(
        "--embed",
        action="store_true",
        help="Generate and save semantic embeddings alongside the index (requires [embed] extra).",
    )

    search_parser = subparsers.add_parser("search", help="Search the current index.")
    search_parser.add_argument("query", help="Search query.")
    search_parser.add_argument("--top-k", type=int, default=8, help="Number of results to return.")
    search_parser.add_argument("--json", action="store_true", help="Emit results as JSON.")

    ask_parser = subparsers.add_parser("ask", help="Ask a question over the current index.")
    ask_parser.add_argument("query", help="Question to answer.")
    ask_parser.add_argument("--top-k", type=int, default=8, help="Number of chunks to use.")

    subparsers.add_parser("stats", help="Show index statistics.")
    subparsers.add_parser("configure", help="Set up your LLM API key (saved to ~/.config/reposcope/.env).")

    args = parser.parse_args(argv)

    try:
        if args.command == "index":
            _index(args.path, args.index_file, embed=args.embed)
        elif args.command == "search":
            _search(args.query, args.top_k, args.index_file, args.json)
        elif args.command == "ask":
            _ask(args.query, args.top_k, args.index_file)
        elif args.command == "stats":
            _stats(args.index_file)
        elif args.command == "configure":
            _configure()
    except Exception as exc:
        print(f"reposcope: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _index(path: Path, index_file: Path, embed: bool = False) -> None:
    index = build_index(path)
    save_index(index, index_file)
    stats = index_stats(index)
    print(f"Indexed {stats['files_indexed']} files into {stats['chunks_indexed']} chunks.")
    print(f"Repo:  {stats['repo_root']}")
    print(f"Index: {index_file}")
    if embed:
        build_and_save_embeddings(index, index_file)


def _resolve_search(chunks, query, top_k, index_file):
    vector_store = load_embeddings(index_file)
    if vector_store is not None:
        from .embedder import embed_query
        query_embedding = embed_query(query)
        return search_chunks_hybrid(chunks, vector_store, query, query_embedding, top_k=top_k)
    return search_chunks(chunks, query, top_k=top_k)


def _search(query: str, top_k: int, index_file: Path, emit_json: bool) -> None:
    index = load_index(index_file)
    results = _resolve_search(index.chunks, query, top_k, index_file)

    if emit_json:
        print(
            json.dumps(
                [
                    {
                        "score": result.score,
                        "path": result.chunk.path,
                        "start_line": result.chunk.start_line,
                        "end_line": result.chunk.end_line,
                        "kind": result.chunk.kind,
                        "name": result.chunk.name,
                        "text": result.chunk.text,
                    }
                    for result in results
                ],
                indent=2,
            )
        )
        return

    if not results:
        print("No matches found.")
        return

    for number, result in enumerate(results, start=1):
        chunk = result.chunk
        print(
            f"{number}. {chunk.path}:{chunk.start_line}-{chunk.end_line} "
            f"{chunk.kind} {chunk.name} score={result.score:.4f}"
        )


def _ask(query: str, top_k: int, index_file: Path) -> None:
    index = load_index(index_file)
    results = _resolve_search(index.chunks, query, top_k, index_file)
    print(answer_from_results(query, results))


def _stats(index_file: Path) -> None:
    index = load_index(index_file)
    stats = index_stats(index)
    from .indexer import embed_path_for
    npy_path = embed_path_for(index_file)
    stats["embeddings"] = str(npy_path) if npy_path.exists() else None
    print(json.dumps(stats, indent=2))


def _configure() -> None:
    import getpass
    from .answer import USER_CONFIG_DIR, USER_CONFIG_ENV

    providers = {
        "1": ("Anthropic Claude", "ANTHROPIC_API_KEY"),
        "2": ("Google Gemini",    "GEMINI_API_KEY"),
        "3": ("OpenAI",           "OPENAI_API_KEY"),
    }

    print("RepoScope — LLM configuration")
    print()
    print("Which provider do you want to use for 'ask' answers?")
    for num, (label, _) in providers.items():
        print(f"  {num}) {label}")
    print()

    choice = input("Enter 1, 2, or 3: ").strip()
    if choice not in providers:
        print("reposcope: invalid choice — run 'reposcope configure' again.", file=sys.stderr)
        raise SystemExit(1)

    label, env_var = providers[choice]
    print()
    api_key = getpass.getpass(f"{label} API key (input hidden): ").strip()
    if not api_key:
        print("reposcope: no key entered — nothing saved.", file=sys.stderr)
        raise SystemExit(1)

    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict[str, str] = {}
    if USER_CONFIG_ENV.is_file():
        for raw_line in USER_CONFIG_ENV.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    existing[env_var] = api_key
    lines = [f"{k}={v}" for k, v in existing.items()]
    USER_CONFIG_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"Saved {env_var} to {USER_CONFIG_ENV}")
    print()
    print("You can now run:")
    print("  reposcope ask \"How does authentication work?\"")


if __name__ == "__main__":
    main()
