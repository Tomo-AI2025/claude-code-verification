"""init command: create .claude-code-verify.yml in the target directory."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()


CONFIG_FILENAME = ".claude-code-verify.yml"


DEFAULT_CONFIG = """\
# .claude-code-verify.yml
# Configuration for claude-code-verify
# See: https://github.com/Tomo-AI2025/claude-code-verification

# Directories to scan for Python code (check-spec, verify-wiring)
codebase_paths:
  - src
  - .

# Directories to exclude from scanning
exclude_paths:
  - tests
  - venv
  - .venv
  - node_modules
  - __pycache__
  - .git

# Additional ambiguous terms to check (fix-terms)
# Default list: phase, mode, stage, state, status, level, type, kind, category, group
custom_ambiguous_terms: []

# Default commit range for clean-commits
default_commit_range: "HEAD~10"

# Similarity threshold for phantom API suggestions (0-100, lower = more lenient)
similarity_threshold: 30
"""


def run(force: bool = False, target_dir: str = ".") -> int:
    """Write the default configuration file.

    Returns 0 on success, 1 if the file exists and ``force`` is False.
    """
    config_path = Path(target_dir) / CONFIG_FILENAME

    if config_path.exists() and not force:
        console.print(
            f"[yellow]{config_path} already exists.[/yellow] "
            f"Re-run with [bold]--force[/bold] to overwrite."
        )
        return 1

    config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")

    console.print(f"[green]Created[/green] [bold]{config_path}[/bold]")
    console.print(
        "[dim]Next: run `claude-code-verify check-spec <spec.md>` to get started.[/dim]"
    )
    return 0
