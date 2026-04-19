"""Python codebase indexer + call graph + orphan detection.

Provides three concerns:

  - :func:`scan_codebase` - build a :class:`CodebaseIndex` with classes,
    top-level functions (with locations), file names, and every referenced
    name across the tree.
  - :func:`find_function_calls` - collect every ``ast.Call`` site, keyed by
    the called name.
  - :func:`find_orphan_functions` - given the index and call map, list
    top-level functions that are defined but never referenced.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from rapidfuzz import fuzz, process


# ---------- data ----------


@dataclass
class ClassInfo:
    name: str
    file: str
    methods: Set[str] = field(default_factory=set)
    properties: Set[str] = field(default_factory=set)


@dataclass
class FunctionDef:
    name: str
    file: str
    line: int
    docstring: Optional[str] = None


@dataclass
class CallSite:
    caller_function: Optional[str]
    file: str
    line_number: int
    call_expression: str


@dataclass
class OrphanInfo:
    function_name: str
    defined_in_file: str
    defined_at_line: int
    docstring: Optional[str] = None


@dataclass
class CodebaseIndex:
    classes: Dict[str, ClassInfo] = field(default_factory=dict)
    functions: Dict[str, List[FunctionDef]] = field(default_factory=dict)
    files: Set[str] = field(default_factory=set)
    used_names: Set[str] = field(default_factory=set)


# ---------- helpers ----------


def _is_property_decorator(decorators: Iterable[ast.expr]) -> bool:
    for d in decorators:
        if isinstance(d, ast.Name) and d.id == "property":
            return True
        if isinstance(d, ast.Attribute) and d.attr == "property":
            return True
    return False


def _collect_class(node: ast.ClassDef, file: str) -> ClassInfo:
    info = ClassInfo(name=node.name, file=file)
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_property_decorator(item.decorator_list):
                info.properties.add(item.name)
            else:
                info.methods.add(item.name)
    return info


def _collect_used_names(tree: ast.AST) -> Set[str]:
    """Every name referenced in the tree: calls, imports, loads, attributes."""
    used: Set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                used.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                used.add(n.func.attr)
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                used.add(alias.asname or alias.name)
        elif isinstance(n, ast.Import):
            for alias in n.names:
                local = alias.asname or alias.name.split(".")[0]
                used.add(local)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            used.add(n.attr)
    return used


def _parse(py_file: Path):
    try:
        source = py_file.read_text(encoding="utf-8")
        return source, ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None, None


# ---------- public API ----------


def scan_codebase(path: str) -> CodebaseIndex:
    """Recursively index Python files under ``path``."""
    index = CodebaseIndex()
    root = Path(path)
    if not root.exists():
        return index

    for py_file in root.rglob("*.py"):
        index.files.add(py_file.name)
        source, tree = _parse(py_file)
        if tree is None:
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                index.classes[node.name] = _collect_class(node, str(py_file))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fd = FunctionDef(
                    name=node.name,
                    file=str(py_file),
                    line=node.lineno,
                    docstring=ast.get_docstring(node),
                )
                index.functions.setdefault(node.name, []).append(fd)

        index.used_names.update(_collect_used_names(tree))

    return index


def find_similar(name: str, candidates: List[str], limit: int = 3,
                 min_score: int = 30) -> List[str]:
    """Return up to ``limit`` candidates most similar to ``name``."""
    if not candidates:
        return []
    matches = process.extract(name, candidates, scorer=fuzz.ratio, limit=limit)
    return [m[0] for m in matches if m[1] >= min_score]


# ---------- call analysis ----------


def _enclosing_function_map(tree: ast.AST) -> Dict[int, str]:
    """Map line number -> enclosing top-level function or ClassName.method."""
    result: Dict[int, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start) or start
            for line in range(start, end + 1):
                result[line] = node.name
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = item.lineno
                    end = getattr(item, "end_lineno", start) or start
                    for line in range(start, end + 1):
                        result[line] = f"{node.name}.{item.name}"
    return result


def _snippet(node: ast.AST, source_lines: List[str]) -> str:
    try:
        line_no = node.lineno - 1
        if 0 <= line_no < len(source_lines):
            return source_lines[line_no].strip()
    except Exception:
        pass
    return ""


def find_function_calls(codebase_path: str) -> Dict[str, List[CallSite]]:
    """Walk ``codebase_path`` and collect call sites keyed by called name."""
    calls: Dict[str, List[CallSite]] = {}
    root = Path(codebase_path)
    if not root.exists():
        return calls

    for py_file in root.rglob("*.py"):
        source, tree = _parse(py_file)
        if tree is None:
            continue

        source_lines = source.splitlines()
        enclosing = _enclosing_function_map(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name: Optional[str] = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if not name:
                continue

            calls.setdefault(name, []).append(CallSite(
                caller_function=enclosing.get(node.lineno),
                file=str(py_file),
                line_number=node.lineno,
                call_expression=_snippet(node, source_lines),
            ))

    return calls


# ---------- orphan detection ----------


_SPECIAL_NAMES = frozenset({
    "main", "run", "setup", "__main__", "__init__",
    "setup_module", "teardown_module",
})


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or name == "conftest.py"


def find_orphan_functions(
    index: CodebaseIndex,
    calls: Dict[str, List[CallSite]],
) -> List[OrphanInfo]:
    """Identify top-level functions defined but never referenced."""
    orphans: List[OrphanInfo] = []

    for name, defs in index.functions.items():
        if name in _SPECIAL_NAMES or name.startswith("_"):
            continue
        if any(_is_test_file(d.file) for d in defs):
            continue
        if name in calls or name in index.used_names:
            continue

        d = defs[0]
        orphans.append(OrphanInfo(
            function_name=name,
            defined_in_file=d.file,
            defined_at_line=d.line,
            docstring=d.docstring,
        ))

    return orphans
