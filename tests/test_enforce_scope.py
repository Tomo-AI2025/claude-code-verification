"""Tests for enforce-scope command."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from git import Repo

from claude_code_verify.commands.enforce_scope import find_violations
from claude_code_verify.core.spec_parser import extract_prohibitions


# ---------- spec parsing ----------


def test_extract_prohibitions_explicit_section():
    text = textwrap.dedent("""\
        # Round 29 Spec

        Add a new function.

        ## DO NOT MODIFY
        - config.py
        - legacy.py
        """)
    prohibitions = extract_prohibitions(text)
    paths = [p.file_path for p in prohibitions]

    assert "config.py" in paths
    assert "legacy.py" in paths
    assert all(p.pattern == "prohibition_section" for p in prohibitions)


def test_extract_prohibitions_inline():
    text = "Do not modify `exam.py`. Don't touch `backtest.py`."
    prohibitions = extract_prohibitions(text)
    paths = [p.file_path for p in prohibitions]

    assert "exam.py" in paths
    assert "backtest.py" in paths
    assert all(p.pattern == "inline" for p in prohibitions)


# ---------- git repo helpers ----------


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


# ---------- violation detection ----------


def test_detects_violation(tmp_path):
    repo = _make_repo(tmp_path)
    _write_and_commit(repo, tmp_path,
                      {"config.py": "INITIAL = 1\n", "main.py": "x = 1\n"},
                      "initial")
    _write_and_commit(repo, tmp_path,
                      {"config.py": "INITIAL = 2\nNEW = 3\n"},
                      "modify config")

    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\n## DO NOT MODIFY\n- config.py\n",
                    encoding="utf-8")

    violations, _ = find_violations(str(spec), "HEAD", str(tmp_path))

    assert len(violations) == 1
    assert "config.py" in violations[0][0]


def test_allows_permitted_changes(tmp_path):
    repo = _make_repo(tmp_path)
    _write_and_commit(repo, tmp_path,
                      {"config.py": "INITIAL = 1\n", "main.py": "x = 1\n"},
                      "initial")
    _write_and_commit(repo, tmp_path,
                      {"main.py": "x = 2\n"},
                      "update main only")

    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\n## DO NOT MODIFY\n- config.py\n",
                    encoding="utf-8")

    violations, _ = find_violations(str(spec), "HEAD", str(tmp_path))

    assert violations == []
