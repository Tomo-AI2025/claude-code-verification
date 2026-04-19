"""verify-wiring command: detect orphan functions (Silent Failure, Pattern #1)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rich.console import Console

from claude_code_verify.core.ast_analyzer import (
    OrphanInfo,
    find_function_calls,
    find_orphan_functions,
    scan_codebase,
)

console = Console()


def _find_main_file(root: Path) -> Optional[Path]:
    for candidate in ("main.py", "__main__.py", "app.py"):
        matches = list(root.rglob(candidate))
        if matches:
            return matches[0]
    return None


def _write_patch(root: Path, orphans: List[OrphanInfo]) -> Path:
    patch_path = root / ".wiring.patch"
    main_file = _find_main_file(root)
    lines: List[str] = ["# verify-wiring suggestions", ""]

    for orphan in orphans:
        lines.append(f"# orphan: {orphan.function_name}")
        lines.append(
            f"# defined: {orphan.defined_in_file}:{orphan.defined_at_line}"
        )
        if orphan.docstring:
            first = orphan.docstring.strip().splitlines()[0]
            lines.append(f"# docstring: {first}")
        if main_file is not None:
            module = Path(orphan.defined_in_file).stem
            lines.append(f"# suggest insertion point: {main_file}")
            lines.append(f"+ from {module} import {orphan.function_name}")
            lines.append(f"+ {orphan.function_name}()")
        else:
            lines.append(
                "# no main.py / __main__.py / app.py - choose an entrypoint manually"
            )
        lines.append("")

    patch_path.write_text("\n".join(lines), encoding="utf-8")
    return patch_path


def run(target_dir: str, fix: bool = False) -> int:
    root = Path(target_dir)
    console.print(f"[bold]verify-wiring[/bold]: scanning {target_dir}")

    index = scan_codebase(target_dir)
    calls = find_function_calls(target_dir)
    orphans = find_orphan_functions(index, calls)

    total_funcs = sum(len(defs) for defs in index.functions.values())
    console.print(
        f"[dim]{total_funcs} top-level function(s) across "
        f"{len(index.files)} file(s).[/dim]\n"
    )

    if not orphans:
        console.print("[green]OK[/green] no orphan functions detected.")
        return 0

    for orphan in orphans:
        console.print(
            f"[yellow]WARN[/yellow] [bold]{orphan.function_name}[/bold] - "
            f"defined at {orphan.defined_in_file}:{orphan.defined_at_line}, "
            f"not called anywhere."
        )
        if orphan.docstring:
            first = orphan.docstring.strip().splitlines()[0]
            console.print(f"       [dim]docstring: {first}[/dim]")

    console.print(
        f"\n[bold]Summary:[/bold] [yellow]{len(orphans)} orphan(s)[/yellow]"
    )

    if fix:
        patch = _write_patch(root, orphans)
        console.print(f"[cyan]Wrote patch to {patch}[/cyan]")

    return 1
