"""check-spec command: detect phantom API references (Pattern #7)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from claude_code_verify.core.ast_analyzer import (
    CodebaseIndex,
    find_similar,
    scan_codebase,
)
from claude_code_verify.core.spec_parser import APIRef, RefType, extract_api_references

console = Console()


@dataclass
class VerifyResult:
    ref: APIRef
    status: str   # "ok" | "phantom"
    message: str = ""
    suggestion: str = ""


def _suggest_member(class_name: str, cls_methods, cls_properties,
                    member: str) -> Optional[str]:
    candidates = sorted(set(cls_methods) | set(cls_properties))
    similar = find_similar(member, candidates)
    if not similar:
        return None
    best = similar[0]
    if best in cls_properties:
        return f"{class_name}.{best}"
    return f"{class_name}.{best}()"


def verify_ref(ref: APIRef, index: CodebaseIndex) -> VerifyResult:
    if ref.ref_type == RefType.FILE:
        if ref.file_name in index.files:
            return VerifyResult(ref=ref, status="ok")
        similar = find_similar(ref.file_name, sorted(index.files))
        return VerifyResult(
            ref=ref,
            status="phantom",
            message="file not found in codebase",
            suggestion=similar[0] if similar else "",
        )

    # METHOD or PROPERTY
    if ref.class_name not in index.classes:
        similar = find_similar(ref.class_name, sorted(index.classes.keys()))
        return VerifyResult(
            ref=ref,
            status="phantom",
            message=f"class '{ref.class_name}' not found",
            suggestion=similar[0] if similar else "",
        )

    cls = index.classes[ref.class_name]

    if ref.ref_type == RefType.METHOD:
        if ref.member_name in cls.methods:
            return VerifyResult(ref=ref, status="ok")
        if ref.member_name in cls.properties:
            return VerifyResult(
                ref=ref,
                status="phantom",
                message=f"'{ref.member_name}' is a property, not a method",
                suggestion=f"{ref.class_name}.{ref.member_name}",
            )
        suggestion = _suggest_member(
            ref.class_name, cls.methods, cls.properties, ref.member_name
        )
        return VerifyResult(
            ref=ref,
            status="phantom",
            message=f"'{ref.member_name}' not found on {ref.class_name}",
            suggestion=suggestion or "",
        )

    # PROPERTY
    if ref.member_name in cls.properties:
        return VerifyResult(ref=ref, status="ok")
    if ref.member_name in cls.methods:
        return VerifyResult(
            ref=ref,
            status="phantom",
            message=f"'{ref.member_name}' is a method, not a property",
            suggestion=f"{ref.class_name}.{ref.member_name}()",
        )
    suggestion = _suggest_member(
        ref.class_name, cls.methods, cls.properties, ref.member_name
    )
    return VerifyResult(
        ref=ref,
        status="phantom",
        message=f"'{ref.member_name}' not found on {ref.class_name}",
        suggestion=suggestion or "",
    )


def _write_patch(spec_path: Path, results: List[VerifyResult]) -> Path:
    patch_path = spec_path.with_suffix(spec_path.suffix + ".patch")
    lines = [f"# check-spec suggestions for {spec_path.name}", ""]
    for res in results:
        if res.status != "phantom" or not res.suggestion:
            continue
        lines.append(f"# L{res.ref.line_number}: {res.ref.context}")
        lines.append(f"-{res.ref.reference}")
        lines.append(f"+{res.suggestion}")
        lines.append("")
    patch_path.write_text("\n".join(lines), encoding="utf-8")
    return patch_path


def run(spec_path: str, fix: bool = False, codebase: str = ".") -> int:
    spec_file = Path(spec_path)
    spec_text = spec_file.read_text(encoding="utf-8")
    refs = extract_api_references(spec_text)
    index = scan_codebase(codebase)

    console.print(f"[bold]check-spec[/bold]: {spec_path} against {codebase}")
    console.print(
        f"[dim]{len(refs)} reference(s) in spec; "
        f"{len(index.classes)} class(es), {len(index.files)} file(s) in codebase.[/dim]\n"
    )

    results = [verify_ref(r, index) for r in refs]

    ok = 0
    phantom = 0
    for res in results:
        ref = res.ref
        if res.status == "ok":
            console.print(
                f"[green]OK[/green]  L{ref.line_number}: `{ref.reference}` "
                f"[dim]({ref.ref_type.value})[/dim]"
            )
            ok += 1
        else:
            phantom += 1
            console.print(
                f"[red]NG[/red]  L{ref.line_number}: [red]`{ref.reference}`[/red] "
                f"[dim]({ref.ref_type.value})[/dim] - {res.message}"
            )
            if res.suggestion:
                console.print(f"      [yellow]suggest[/yellow] `{res.suggestion}`")

    console.print(
        f"\n[bold]Summary:[/bold] {ok} OK, "
        f"[red]{phantom} phantom[/red]"
    )

    if fix and phantom > 0:
        patch_path = _write_patch(spec_file, results)
        console.print(f"[cyan]Wrote suggestions to {patch_path}[/cyan]")

    return 0 if phantom == 0 else 1
