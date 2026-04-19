"""clean-commits command: detect commit messages that don't match their diff.

History is never rewritten automatically. ``--fix`` only writes a
``.commit-suggestions.md`` report for the user to act on with
``git commit --amend`` or ``git rebase -i``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from claude_code_verify.core.git_ops import (
    CommitInfo,
    GitOpsError,
    get_commit_history,
)

console = Console()


# ---------- verb extraction ----------


_VERB_PATTERNS: Dict[str, str] = {
    "integrate": "integrate", "integrates": "integrate",
    "integrated": "integrate", "integrating": "integrate",
    "wire": "integrate", "wires": "integrate", "wired": "integrate",
    "wiring": "integrate", "connect": "integrate", "connects": "integrate",
    "hook": "integrate", "hooks": "integrate",
    "fix": "fix", "fixes": "fix", "fixed": "fix",
    "bugfix": "fix", "patch": "fix",
    "resolve": "fix", "resolves": "fix", "resolved": "fix",
    "refactor": "refactor", "refactors": "refactor", "refactored": "refactor",
    "rewrite": "refactor", "restructure": "refactor",
    "implement": "implement", "implements": "implement",
    "implemented": "implement",
    "add": "add", "adds": "add", "added": "add",
    "introduce": "add", "introduces": "add", "introduced": "add",
    "create": "add", "creates": "add",
}

_CONVENTIONAL_PREFIX_RE = re.compile(
    r"^(feat|fix|refactor|test|docs|chore|add|update|build|perf|style|revert)"
    r"(?:\([^)]+\))?:\s*(.+)",
    re.IGNORECASE,
)


def extract_verb(message: str) -> Optional[str]:
    """Return the canonical action verb of a commit message, or None."""
    msg = message.strip()

    m = _CONVENTIONAL_PREFIX_RE.match(msg)
    if m:
        prefix = m.group(1).lower()
        if prefix == "feat":
            return "implement"
        return _VERB_PATTERNS.get(prefix, prefix)

    for word in re.findall(r"\b[A-Za-z]+\b", msg.lower())[:4]:
        if word in _VERB_PATTERNS:
            return _VERB_PATTERNS[word]

    return None


# ---------- diff analysis ----------


_SKIP_PREFIXES = (
    "diff ", "index ", "@@", "+++", "---",
    "new file", "deleted file", "Binary ", "similarity ",
    "rename from", "rename to",
)
_DEF_RE = re.compile(r"^\s*(async\s+)?def\s+\w+")


@dataclass
class DiffSignals:
    additions: int
    deletions: int
    new_defs: int
    removed_defs: int
    new_calls: int


def diff_signals(diff_text: str) -> DiffSignals:
    """Extract coarse signals from a unified diff."""
    added: List[str] = []
    deleted: List[str] = []

    for line in diff_text.splitlines():
        if any(line.startswith(p) for p in _SKIP_PREFIXES):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            deleted.append(line[1:])

    new_defs = sum(1 for l in added if _DEF_RE.match(l))
    removed_defs = sum(1 for l in deleted if _DEF_RE.match(l))

    new_calls = 0
    for l in added:
        stripped = l.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("def ", "async def ", "class ", "import ", "from ")):
            continue
        if re.search(r"[A-Za-z_]\w*\s*\(", stripped):
            new_calls += 1

    return DiffSignals(
        additions=len(added),
        deletions=len(deleted),
        new_defs=new_defs,
        removed_defs=removed_defs,
        new_calls=new_calls,
    )


# ---------- consistency judgment ----------


@dataclass
class Judgment:
    consistent: bool
    reason: str = ""
    suggested_verb: str = ""


def judge_consistency(verb: str, signals: DiffSignals) -> Judgment:
    if verb == "integrate":
        if signals.new_defs > 0 and signals.new_calls == 0:
            return Judgment(
                consistent=False,
                reason="claim is 'integrate' but diff adds definitions without call sites",
                suggested_verb="add",
            )
        return Judgment(consistent=True)

    if verb == "fix":
        if signals.additions > 0 and signals.deletions == 0:
            return Judgment(
                consistent=False,
                reason="claim is 'fix' but diff is pure addition (no lines removed)",
                suggested_verb="add",
            )
        return Judgment(consistent=True)

    if verb == "refactor":
        if signals.deletions == 0:
            return Judgment(
                consistent=False,
                reason="claim is 'refactor' but diff has no removals",
                suggested_verb="add",
            )
        return Judgment(consistent=True)

    if verb == "implement":
        if signals.new_defs == 0:
            return Judgment(
                consistent=False,
                reason="claim is 'implement' but diff has no new function definitions",
                suggested_verb="update",
            )
        return Judgment(consistent=True)

    if verb == "add":
        if signals.additions > 0 and signals.deletions > signals.additions:
            return Judgment(
                consistent=False,
                reason="claim is 'add' but more lines deleted than added",
                suggested_verb="remove",
            )
        return Judgment(consistent=True)

    return Judgment(consistent=True)


# ---------- message suggestion ----------


def suggest_message(original: str, signals: DiffSignals) -> str:
    """Produce a short content-based description of what the diff actually does."""
    parts: List[str] = []
    if signals.new_defs > 0:
        parts.append(f"define {signals.new_defs} function(s)")
    if signals.new_calls > 0:
        parts.append(f"add {signals.new_calls} call site(s)")
    if signals.removed_defs > 0:
        parts.append(f"remove {signals.removed_defs} function(s)")
    if signals.deletions > 0 and signals.removed_defs == 0:
        parts.append(f"remove {signals.deletions} line(s)")
    if signals.additions > 0 and signals.new_defs == 0 and signals.new_calls == 0:
        parts.append(f"add {signals.additions} line(s)")
    if not parts:
        parts.append("no content-level change detected")
    return "; ".join(parts)


# ---------- report output ----------


Issue = Tuple[CommitInfo, str, DiffSignals, Judgment]


def _write_suggestions_file(issues: List[Issue], path: Path) -> None:
    lines = [
        "# Commit Message Suggestions",
        "",
        "Generated by `claude-code-verify clean-commits`.",
        "**History is not rewritten automatically.**",
        "For the latest commit: `git commit --amend -m \"<new message>\"`.",
        "For older commits: `git rebase -i <base>` and reword.",
        "",
        "---",
        "",
    ]
    for commit, verb, signals, judgment in issues:
        lines.append(f"## {commit.sha}: {commit.message}")
        lines.append("")
        lines.append(f"- **claim verb**: `{verb}`")
        lines.append(f"- **issue**: {judgment.reason}")
        lines.append(f"- **diff shows**: {suggest_message(commit.message, signals)}")
        if judgment.suggested_verb:
            lines.append(f"- **suggested verb**: `{judgment.suggested_verb}`")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------- CLI entry ----------


def run(since: str = "HEAD~10", fix: bool = False) -> int:
    try:
        commits = get_commit_history(since)
    except GitOpsError as e:
        console.print(f"[red]git error:[/red] {e}")
        return 2

    console.print(f"[bold]clean-commits[/bold]: scanning {since}..HEAD")
    console.print(f"[dim]{len(commits)} commit(s) to check.[/dim]\n")

    if not commits:
        console.print("[green]OK[/green] no commits in range.")
        return 0

    issues: List[Issue] = []
    for commit in commits:
        verb = extract_verb(commit.message)
        if verb is None:
            console.print(f"[dim]OK[/dim] {commit.sha} {commit.message}")
            continue

        signals = diff_signals(commit.diff_text)
        judgment = judge_consistency(verb, signals)

        if judgment.consistent:
            console.print(f"[green]OK[/green] {commit.sha} {commit.message}")
            continue

        issues.append((commit, verb, signals, judgment))
        console.print(
            f"[yellow]WARN[/yellow] {commit.sha} {commit.message}"
        )
        console.print(f"       [dim]{judgment.reason}[/dim]")
        console.print(
            f"       [cyan]diff shows:[/cyan] {suggest_message(commit.message, signals)}"
        )

    console.print(
        f"\n[bold]Summary:[/bold] {len(commits) - len(issues)} OK, "
        f"[yellow]{len(issues)} suspicious[/yellow]"
    )

    if fix and issues:
        path = Path(".commit-suggestions.md")
        _write_suggestions_file(issues, path)
        console.print(f"[cyan]Wrote {path}[/cyan]")
        console.print(
            "[dim]History is NOT rewritten automatically. "
            "Use `git commit --amend` or `git rebase -i`.[/dim]"
        )

    return 0 if not issues else 1
