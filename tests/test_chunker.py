import textwrap
from pathlib import Path

import pytest

from reposcope.chunker import chunk_file


def test_python_function_and_class(tmp_path):
    src = tmp_path / "sample.py"
    src.write_text(textwrap.dedent("""\
        def greet(name):
            return f"hello {name}"

        class Greeter:
            def hello(self):
                return "hi"
    """))
    chunks = chunk_file(src, tmp_path)
    kinds = {c.kind for c in chunks}
    assert "function" in kinds
    assert "class" in kinds


def test_python_async_function(tmp_path):
    src = tmp_path / "async_sample.py"
    src.write_text(textwrap.dedent("""\
        async def fetch_data(url):
            return await client.get(url)
    """))
    chunks = chunk_file(src, tmp_path)
    assert any(c.kind == "function" and c.name == "fetch_data" for c in chunks)


def test_typescript_function(tmp_path):
    src = tmp_path / "app.ts"
    src.write_text(textwrap.dedent("""\
        export function formatDate(date: Date): string {
            return date.toISOString();
        }

        const multiply = (a: number, b: number) => a * b;
    """))
    chunks = chunk_file(src, tmp_path)
    names = {c.name for c in chunks}
    assert "formatDate" in names


def test_markdown_falls_back_to_line_window(tmp_path):
    src = tmp_path / "README.md"
    src.write_text("# Title\n\nSome content.\n")
    chunks = chunk_file(src, tmp_path)
    assert chunks
    assert all(c.kind == "block" for c in chunks)


def test_empty_file_returns_no_chunks(tmp_path):
    src = tmp_path / "empty.py"
    src.write_text("")
    chunks = chunk_file(src, tmp_path)
    assert chunks == []


def test_chunk_path_is_relative(tmp_path):
    src = tmp_path / "sub" / "module.py"
    src.parent.mkdir()
    src.write_text("def foo(): pass\n")
    chunks = chunk_file(src, tmp_path)
    assert chunks
    assert not chunks[0].path.startswith("/")
    assert "sub/module.py" in chunks[0].path


def test_csharp_method_chunking(tmp_path):
    src = tmp_path / "Controller.cs"
    src.write_text(textwrap.dedent("""\
        public class AuthController
        {
            public IActionResult Login(LoginRequest request)
            {
                return Ok();
            }
        }
    """))
    chunks = chunk_file(src, tmp_path)
    kinds = {c.kind for c in chunks}
    assert "class" in kinds or "method" in kinds
