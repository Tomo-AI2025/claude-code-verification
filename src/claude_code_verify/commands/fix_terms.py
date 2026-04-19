"""fix-terms command: detect and fix terminology ambiguity (Pattern #9)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from rich.console import Console

from claude_code_verify.core.spec_parser import (
    AmbiguousTerm,
    extract_ambiguous_terms,
)

console = Console()


_SECTION_HEADING = "## Terminology Definitions"


def _entry_line(meaning: str) -> str:
    return f"- **{meaning}**: <define here>"


def _collect_new_entries(terms: List[AmbiguousTerm]) -> List[str]:
    entries: List[str] = []
    seen = set()
    for term in terms:
        for meaning in term.suggested_meanings:
            line = _entry_line(meaning)
            if line in seen:
                continue
            seen.add(line)
            entries.append(line)
    return entries


def _find_section(lines: List[str]) -> Tuple[int, int]:
    """Return (start, end) indices of an existing Terminology Definitions
    section, or (-1, -1) if absent. ``end`` is exclusive and points at the
    next heading or end of file.
    """
    start = -1
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## terminology definitions"):
            start = i
            break
    if start < 0:
        return (-1, -1)

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return (start, end)


def _insertion_point(lines: List[str]) -> int:
    """Where to insert a new section: after the H1 title and its blank line."""
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            insert_at = i + 1
            break
    if insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    return insert_at


def insert_or_update_definitions(text: str, terms: List[AmbiguousTerm]) -> str:
    """Insert or merge a Terminology Definitions section."""
    if not terms:
        return text

    new_entries = _collect_new_entries(terms)
    lines = text.splitlines()
    had_trailing_newline = text.endswith("\n")

    start, end = _find_section(lines)
    if start >= 0:
        existing = {
            ln.strip() for ln in lines[start + 1:end]
            if ln.strip().startswith("- **")
        }
        to_add = [e for e in new_entries if e not in existing]
        if not to_add:
            return text
        # Insert before `end`, trimming trailing blank lines in the section
        section = lines[start:end]
        while section and not section[-1].strip():
            section.pop()
        section.extend(to_add)
        section.append("")
        rebuilt = lines[:start] + section + lines[end:]
    else:
        insert_at = _insertion_point(lines)
        section = [_SECTION_HEADING, ""] + new_entries + [""]
        rebuilt = lines[:insert_at] + section + lines[insert_at:]

    result = "\n".join(rebuilt)
    if had_trailing_newline and not result.endswith("\n"):
        result += "\n"
    return result


def run(spec_path: str, fix: bool = False) -> int:
    spec_file = Path(spec_path)
    text = spec_file.read_text(encoding="utf-8")
    terms = extract_ambiguous_terms(text)

    console.print(f"[bold]fix-terms[/bold]: analyzing {spec_path}")

    if not terms:
        console.print("[green]OK[/green] no ambiguous terms detected.")
        return 0

    for term in terms:
        console.print(
            f"[yellow]AMBIG[/yellow] [bold]{term.term}[/bold] - "
            f"{len(term.occurrences)} occurrence(s) in distinct contexts"
        )
        for occ in term.occurrences:
            console.print(
                f"       L{occ.line_number}: [dim]{occ.surrounding_text}[/dim]"
            )
        console.print(
            f"       [cyan]suggest:[/cyan] "
            f"{', '.join(term.suggested_meanings)}"
        )

    console.print(
        f"\n[bold]Summary:[/bold] [yellow]{len(terms)} ambiguous term(s)[/yellow]"
    )

    if fix:
        new_text = insert_or_update_definitions(text, terms)
        if new_text == text:
            console.print("[dim]No new definitions to add.[/dim]")
        else:
            spec_file.write_text(new_text, encoding="utf-8")
            console.print(
                f"[cyan]Updated {spec_path} with Terminology Definitions section[/cyan]"
            )

    return 1
