"""enforce-scope command: revert scope violations (Pattern #8)."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import List, Tuple

from rich.console import Console

from claude_code_verify.core.git_ops import (
    GitOpsError,
    generate_revert_patch,
    get_changed_files,
)
from claude_code_verify.core.spec_parser import Prohibition, extract_prohibitions

console = Console()


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def matches_prohibition(changed_file: str, prohibition: Prohibition) -> bool:
    """Return True if ``changed_file`` is restricted by ``prohibition``."""
    changed = _normalize(changed_file)
    rule = _normalize(prohibition.file_path).strip()

    if not rule:
        return False

    if "*" in rule or "?" in rule:
        return fnmatch(changed, rule)

    if rule.endswith("/"):
        return changed.startswith(rule) or f"/{rule}" in f"/{changed}"

    if changed == rule or changed.endswith("/" + rule):
        return True

    if "/" not in rule:
        return PurePosixPath(changed).name == rule

    return False


def find_violations(
    spec_path: str,
    commit: str = "HEAD",
    repo_path: str = ".",
) -> Tuple[List[Tuple[str, Prohibition]], List[Prohibition]]:
    """Return (violations, all_prohibitions)."""
    spec_text = Path(spec_path).read_text(encoding="utf-8")
    prohibitions = extract_prohibitions(spec_text)
    changed = get_changed_files(commit, repo_path)

    violations: List[Tuple[str, Prohibition]] = []
    for cf in changed:
        for p in prohibitions:
            if matches_prohibition(cf, p):
                violations.append((cf, p))
                break

    return violations, prohibitions


def run(spec: str, commit: str = "HEAD", fix: bool = False) -> int:
    try:
        violations, prohibitions = find_violations(spec, commit)
    except GitOpsError as e:
        console.print(f"[red]git error:[/red] {e}")
        return 2
    except FileNotFoundError as e:
        console.print(f"[red]spec not found:[/red] {e}")
        return 2

    console.print(f"[bold]enforce-scope[/bold]: checking {commit} against {spec}")
    console.print(
        f"[dim]{len(prohibitions)} prohibition(s) declared in spec.[/dim]\n"
    )

    if not violations:
        console.print("[green]OK[/green] no scope violations.")
        return 0

    for cf, p in violations:
        console.print(
            f"[red]VIOLATION[/red] [bold]{cf}[/bold] "
            f"(rule at spec L{p.source_line}, {p.pattern})"
        )
        console.print(f"       [dim]{p.source_text}[/dim]")

    console.print(
        f"\n[bold]Summary:[/bold] [red]{len(violations)} violation(s)[/red]"
    )

    if fix:
        violated_files = sorted({v[0] for v in violations})
        try:
            patch = generate_revert_patch(commit, violated_files)
        except GitOpsError as e:
            console.print(f"[red]patch generation failed:[/red] {e}")
            return 1
        patch_path = Path(".scope.patch")
        patch_path.write_text(patch, encoding="utf-8")
        console.print(
            f"[cyan]Wrote revert patch to {patch_path}[/cyan] "
            f"({len(violated_files)} file(s))"
        )

    return 1
