"""Markdown spec parser.

Three public extractors:

  - :func:`extract_api_references` - backtick-delimited API references
    (method / property / file) outside fenced code blocks.
  - :func:`extract_prohibitions` - "DO NOT MODIFY" / "Out of Scope" sections
    and inline "do not modify `foo.py`" mentions.
  - :func:`extract_ambiguous_terms` - words from a canonical list that
    appear in multiple distinct contexts within the same spec.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Optional, Set, Tuple


# ---------- API references ----------


class RefType(str, Enum):
    METHOD = "method"
    PROPERTY = "property"
    FILE = "file"


@dataclass
class APIRef:
    reference: str
    ref_type: RefType
    line_number: int
    context: str
    class_name: str = ""
    member_name: str = ""
    file_name: str = ""


_METHOD_RE = re.compile(r"^([A-Z][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)\(\)$")
_PROPERTY_RE = re.compile(r"^([A-Z][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)$")
_FILE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*\.py)$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _classify(token: str, line_number: int, context: str) -> Optional[APIRef]:
    m = _METHOD_RE.match(token)
    if m:
        return APIRef(
            reference=token,
            ref_type=RefType.METHOD,
            line_number=line_number,
            context=context,
            class_name=m.group(1),
            member_name=m.group(2),
        )

    m = _PROPERTY_RE.match(token)
    if m:
        return APIRef(
            reference=token,
            ref_type=RefType.PROPERTY,
            line_number=line_number,
            context=context,
            class_name=m.group(1),
            member_name=m.group(2),
        )

    m = _FILE_RE.match(token)
    if m:
        return APIRef(
            reference=token,
            ref_type=RefType.FILE,
            line_number=line_number,
            context=context,
            file_name=token,
        )

    return None


def extract_api_references(text: str) -> List[APIRef]:
    """Return API references found in ``text``.

    Skips lines inside fenced code blocks (``` ... ```).
    """
    refs: List[APIRef] = []
    in_code_block = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        context = line.strip()
        for match in _BACKTICK_RE.finditer(line):
            token = match.group(1).strip()
            ref = _classify(token, line_number, context)
            if ref is not None:
                refs.append(ref)

    return refs


# ---------- Prohibitions ----------


@dataclass
class Prohibition:
    file_path: str
    source_line: int
    source_text: str
    pattern: str   # "prohibition_section" | "out_of_scope" | "inline"


_HEADING_RE = re.compile(r"^#+\s+")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s*$")
_INLINE_PROHIBITION_RE = re.compile(
    r"(?i)(?:do\s*not|don'?t|dont)\s+(?:modify|touch|change|edit)\s+`([^`]+)`"
)
_PROHIBITION_PHRASES = (
    ("out of scope", "out_of_scope"),
    ("don't modify", "prohibition_section"),
    ("don't touch", "prohibition_section"),
    ("don't change", "prohibition_section"),
    ("don't edit", "prohibition_section"),
    ("do not modify", "prohibition_section"),
    ("do not touch", "prohibition_section"),
    ("do not change", "prohibition_section"),
    ("do not edit", "prohibition_section"),
)


def _prohibition_kind(heading_line: str) -> Optional[str]:
    lower = heading_line.lstrip("# ").strip().lower()
    for phrase, kind in _PROHIBITION_PHRASES:
        if phrase in lower:
            return kind
    return None


def _path_from_bullet(bullet_text: str) -> Optional[str]:
    m = re.search(r"`([^`]+)`", bullet_text)
    if m:
        return m.group(1).strip()
    tokens = bullet_text.split()
    if not tokens:
        return None
    return tokens[0].strip(".,;:()")


def extract_prohibitions(text: str) -> List[Prohibition]:
    """Extract prohibitions (explicit sections + inline mentions) from spec."""
    results: List[Prohibition] = []
    in_section = False
    section_pattern = ""

    for i, line in enumerate(text.splitlines(), start=1):
        if _HEADING_RE.match(line):
            kind = _prohibition_kind(line)
            if kind:
                in_section = True
                section_pattern = kind
            else:
                in_section = False
            continue

        if in_section:
            bullet_match = _BULLET_RE.match(line)
            if bullet_match:
                path = _path_from_bullet(bullet_match.group(1))
                if path:
                    results.append(Prohibition(
                        file_path=path,
                        source_line=i,
                        source_text=line.strip(),
                        pattern=section_pattern,
                    ))
                continue
            if not line.strip():
                continue
            in_section = False

        for m in _INLINE_PROHIBITION_RE.finditer(line):
            results.append(Prohibition(
                file_path=m.group(1).strip(),
                source_line=i,
                source_text=line.strip(),
                pattern="inline",
            ))

    return results


# ---------- Ambiguous terms ----------


@dataclass
class TermOccurrence:
    line_number: int
    surrounding_text: str


@dataclass
class AmbiguousTerm:
    term: str
    occurrences: List[TermOccurrence] = field(default_factory=list)
    suggested_meanings: List[str] = field(default_factory=list)


DEFAULT_AMBIGUOUS_TERMS = frozenset({
    "phase", "mode", "stage", "state", "status",
    "level", "type", "kind", "category", "group",
})

_STOPWORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "of", "to", "for", "with",
    "and", "or", "but", "is", "are", "was", "were", "be", "been", "being",
    "during", "before", "after", "when", "while", "as", "then", "than",
    "this", "that", "these", "those", "it", "its", "their", "them",
    "we", "our", "you", "your", "i", "me", "my",
    "by", "from", "into", "onto", "out",
})

_TOKEN_RE = re.compile(r"\b\w+\b")
_CONTEXT_WINDOW = 25   # characters on each side for surrounding_text


def _is_useful_modifier(word: str) -> bool:
    if not word:
        return False
    if word in _STOPWORDS:
        return False
    if word.isdigit():
        return False
    return True


def extract_ambiguous_terms(
    text: str,
    terms: Iterable[str] = DEFAULT_AMBIGUOUS_TERMS,
) -> List[AmbiguousTerm]:
    """Detect canonical terms that appear in at least two distinct contexts.

    Skips fenced code blocks. Case-insensitive. A term is "ambiguous" if the
    set of (prev_word, next_word) signatures it appears with has size >= 2.
    """
    term_set = {t.lower() for t in terms}
    in_code_block = False

    # term -> list of (line_number, prev_word, next_word, surrounding_text)
    collected: "dict[str, List[Tuple[int, str, str, str]]]" = defaultdict(list)

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        tokens = list(_TOKEN_RE.finditer(line))
        for i, match in enumerate(tokens):
            word = match.group(0).lower()
            if word not in term_set:
                continue

            prev_word = tokens[i - 1].group(0).lower() if i > 0 else ""
            next_word = tokens[i + 1].group(0).lower() if i < len(tokens) - 1 else ""

            left = max(0, match.start() - _CONTEXT_WINDOW)
            right = min(len(line), match.end() + _CONTEXT_WINDOW)
            surrounding = line[left:right].strip()

            collected[word].append((line_number, prev_word, next_word, surrounding))

    results: List[AmbiguousTerm] = []
    for term, occs in collected.items():
        signatures: Set[Tuple[str, str]] = {(p, n) for (_, p, n, _) in occs}
        if len(signatures) < 2:
            continue

        modifiers: Set[str] = set()
        for (_, prev, nxt, _) in occs:
            for word in (prev, nxt):
                if _is_useful_modifier(word):
                    modifiers.add(word)

        suggested = [f"{term} ({m})" for m in sorted(modifiers)]
        while len(suggested) < 2:
            suggested.append(f"{term} (meaning {len(suggested) + 1})")

        results.append(AmbiguousTerm(
            term=term,
            occurrences=[
                TermOccurrence(line_number=ln, surrounding_text=sur)
                for (ln, _, _, sur) in occs
            ],
            suggested_meanings=suggested,
        ))

    results.sort(key=lambda t: t.term)
    return results
