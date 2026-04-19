"""Tests for verify-wiring command."""

from __future__ import annotations

import textwrap

from claude_code_verify.core.ast_analyzer import (
    find_function_calls,
    find_orphan_functions,
    scan_codebase,
)


def test_find_function_calls(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(textwrap.dedent("""\
        def helper():
            return 1

        def main():
            return helper()
        """))

    calls = find_function_calls(str(tmp_path))

    assert "helper" in calls
    assert len(calls["helper"]) == 1
    assert calls["helper"][0].caller_function == "main"


def test_detects_orphan_function(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(textwrap.dedent('''\
        def used():
            return 1


        def orphan():
            """An orphan."""
            return 2


        x = used()
        '''))

    index = scan_codebase(str(tmp_path))
    calls = find_function_calls(str(tmp_path))
    orphans = find_orphan_functions(index, calls)

    names = [o.function_name for o in orphans]
    assert "orphan" in names
    assert "used" not in names


def test_ignores_test_files(tmp_path):
    f = tmp_path / "test_mod.py"
    f.write_text(textwrap.dedent("""\
        def test_something():
            assert 1 == 1
        """))

    index = scan_codebase(str(tmp_path))
    calls = find_function_calls(str(tmp_path))
    orphans = find_orphan_functions(index, calls)

    names = [o.function_name for o in orphans]
    assert "test_something" not in names


def test_recognizes_imported_calls(tmp_path):
    lib = tmp_path / "lib.py"
    lib.write_text(textwrap.dedent("""\
        def execute_rebalance():
            return 1
        """))

    main = tmp_path / "main.py"
    main.write_text(textwrap.dedent("""\
        from lib import execute_rebalance


        def main():
            return execute_rebalance()
        """))

    index = scan_codebase(str(tmp_path))
    calls = find_function_calls(str(tmp_path))
    orphans = find_orphan_functions(index, calls)

    names = [o.function_name for o in orphans]
    assert "execute_rebalance" not in names
