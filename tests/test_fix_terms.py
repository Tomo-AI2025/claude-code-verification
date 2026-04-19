"""Tests for fix-terms command."""

from __future__ import annotations

import textwrap

from claude_code_verify.commands.fix_terms import run
from claude_code_verify.core.spec_parser import extract_ambiguous_terms


def test_extract_ambiguous_terms():
    text = textwrap.dedent("""\
        During Phase 3, the system enters operational phase 3.
        Verify the phase-boundary logic.
        Update operational phase transitions.
        """)
    terms = extract_ambiguous_terms(text)
    names = [t.term for t in terms]

    assert "phase" in names
    phase = next(t for t in terms if t.term == "phase")
    assert len(phase.occurrences) >= 3


def test_ignores_unambiguous_terms():
    text = "During Phase 3, the system starts."
    terms = extract_ambiguous_terms(text)
    names = [t.term for t in terms]

    assert "phase" not in names


def test_ignores_code_blocks():
    text = textwrap.dedent("""\
        Outside: operational phase one.

        ```python
        def compute_phase():
            phase = "alpha"
            phase = "beta"
            return phase
        ```
        """)
    terms = extract_ambiguous_terms(text)
    names = [t.term for t in terms]

    assert "phase" not in names


def test_generates_definitions_section(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(textwrap.dedent("""\
        # Round 17 Spec

        During Phase 3, verify operational phase 5.
        """), encoding="utf-8")

    exit_code = run(str(spec), fix=True)
    new_content = spec.read_text(encoding="utf-8")

    assert exit_code == 1
    assert "## Terminology Definitions" in new_content
    assert "phase" in new_content.lower()
    # Original content preserved
    assert "# Round 17 Spec" in new_content
    assert "operational phase 5" in new_content
