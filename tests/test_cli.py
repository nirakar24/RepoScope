import json
import textwrap
from pathlib import Path

import pytest

from reposcope.cli import main


@pytest.fixture()
def sample_repo(tmp_path):
    src = tmp_path / "app.py"
    src.write_text(textwrap.dedent("""\
        def authenticate(user, password):
            return check_hash(password, user.password_hash)

        class UserService:
            def create_user(self, email, password):
                return User(email=email)
    """))
    return tmp_path


@pytest.fixture()
def index_file(tmp_path):
    return tmp_path / ".reposcope" / "test.json"


def test_index_creates_json(sample_repo, index_file):
    main(["--index-file", str(index_file), "index", str(sample_repo)])
    assert index_file.exists()
    data = json.loads(index_file.read_text())
    assert "chunks" in data
    assert data["files_indexed"] >= 1
    assert len(data["chunks"]) >= 1


def test_stats_after_index(sample_repo, index_file, capsys):
    main(["--index-file", str(index_file), "index", str(sample_repo)])
    capsys.readouterr()  # discard index output
    main(["--index-file", str(index_file), "stats"])
    out = capsys.readouterr().out
    stats = json.loads(out)
    assert stats["chunks_indexed"] >= 1
    assert "python" in stats["languages"]


def test_search_returns_results(sample_repo, index_file, capsys):
    main(["--index-file", str(index_file), "index", str(sample_repo)])
    main(["--index-file", str(index_file), "search", "authenticate user"])
    out = capsys.readouterr().out
    assert "authenticate" in out


def test_search_json_output(sample_repo, index_file, capsys):
    main(["--index-file", str(index_file), "index", str(sample_repo)])
    capsys.readouterr()  # discard index output
    main(["--index-file", str(index_file), "search", "authenticate", "--json"])
    out = capsys.readouterr().out
    results = json.loads(out)
    assert isinstance(results, list)
    if results:
        assert "path" in results[0]
        assert "score" in results[0]
        assert "text" in results[0]


def test_search_no_match_prints_message(sample_repo, index_file, capsys):
    main(["--index-file", str(index_file), "index", str(sample_repo)])
    main(["--index-file", str(index_file), "search", "zxqwerty_nonexistent_xyz"])
    out = capsys.readouterr().out
    assert "No matches" in out


def test_index_missing_path_raises(tmp_path, index_file):
    with pytest.raises(SystemExit):
        main(["--index-file", str(index_file), "index", str(tmp_path / "nonexistent")])
