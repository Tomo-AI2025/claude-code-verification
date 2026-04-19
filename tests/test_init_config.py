"""Tests for init command."""

from __future__ import annotations

import yaml

from claude_code_verify.commands.init_config import CONFIG_FILENAME, run


def test_creates_default_config(tmp_path):
    exit_code = run(target_dir=str(tmp_path))
    config_path = tmp_path / CONFIG_FILENAME

    assert exit_code == 0
    assert config_path.exists()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "codebase_paths" in data
    assert "exclude_paths" in data
    assert "default_commit_range" in data
    assert "similarity_threshold" in data
    assert data["similarity_threshold"] == 30


def test_refuses_overwrite_without_force(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("existing: content\n",
                                            encoding="utf-8")

    exit_code = run(target_dir=str(tmp_path))

    assert exit_code == 1
    assert (tmp_path / CONFIG_FILENAME).read_text(encoding="utf-8") == "existing: content\n"


def test_force_overwrite(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("existing: content\n",
                                            encoding="utf-8")

    exit_code = run(target_dir=str(tmp_path), force=True)
    new_content = (tmp_path / CONFIG_FILENAME).read_text(encoding="utf-8")

    assert exit_code == 0
    assert "existing: content" not in new_content
    assert "codebase_paths" in new_content
