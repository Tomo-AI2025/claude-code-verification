"""Tests for clean-commits command."""

from __future__ import annotations

from pathlib import Path

from git import Repo

from claude_code_verify.commands.clean_commits import (
    DiffSignals,
    diff_signals,
    extract_verb,
    judge_consistency,
    suggest_message,
)
from claude_code_verify.core.git_ops import get_commit_history


def _make_repo(tmp_path: Path) -> Repo:
    repo = Repo.init(tmp_path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "test")
        cw.set_value("user", "email", "test@example.com")
    return repo


def _write_and_commit(repo: Repo, tmp_path: Path, files: dict, message: str):
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    repo.index.add(list(files.keys()))
    repo.index.commit(message)


def test_extracts_commit_info(tmp_path):
    repo = _make_repo(tmp_path)
    _write_and_commit(repo, tmp_path, {"f.py": "x = 1\n"}, "initial")
    _write_and_commit(repo, tmp_path, {"f.py": "x = 2\n"}, "update x value")

    history = get_commit_history("HEAD~1", str(tmp_path))

    assert len(history) == 1
    assert history[0].message == "update x value"
    assert "f.py" in history[0].changed_files
    assert history[0].additions >= 1
    assert "diff --git" in history[0].diff_text


def test_detects_add_without_integration(tmp_path):
    repo = _make_repo(tmp_path)
    _write_and_commit(repo, tmp_path,
                      {"core.py": "def base():\n    return 0\n"}, "initial")
    _write_and_commit(repo, tmp_path,
                      {"core.py":
                       "def base():\n    return 0\n\n\ndef helper():\n    return 1\n"},
                      "integrate helper into main flow")

    history = get_commit_history("HEAD~1", str(tmp_path))
    commit = history[0]
    verb = extract_verb(commit.message)
    signals = diff_signals(commit.diff_text)
    judgment = judge_consistency(verb, signals)

    assert verb == "integrate"
    assert signals.new_defs >= 1
    assert signals.new_calls == 0
    assert not judgment.consistent
    assert "integrate" in judgment.reason


def test_valid_add_message(tmp_path):
    repo = _make_repo(tmp_path)
    _write_and_commit(repo, tmp_path, {"m.py": "x = 1\n"}, "initial")
    _write_and_commit(repo, tmp_path,
                      {"m.py": "x = 1\ny = 2\nz = 3\n"},
                      "add y and z constants")

    history = get_commit_history("HEAD~1", str(tmp_path))
    commit = history[0]
    verb = extract_verb(commit.message)
    signals = diff_signals(commit.diff_text)
    judgment = judge_consistency(verb, signals)

    assert verb == "add"
    assert judgment.consistent


def test_generates_suggestion():
    signals = DiffSignals(
        additions=8, deletions=0, new_defs=1, removed_defs=0, new_calls=0,
    )
    suggestion = suggest_message("integrate helper into main", signals)

    assert "define" in suggestion.lower()
    assert "1 function" in suggestion
