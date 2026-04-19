"""Tests for check-spec command."""

from __future__ import annotations

import textwrap

from claude_code_verify.commands.check_spec import verify_ref
from claude_code_verify.core.ast_analyzer import scan_codebase
from claude_code_verify.core.spec_parser import (
    APIRef,
    RefType,
    extract_api_references,
)


def test_extract_api_references():
    text = "Call `MyClass.method()` to do the thing."
    refs = extract_api_references(text)

    assert len(refs) == 1
    assert refs[0].reference == "MyClass.method()"
    assert refs[0].ref_type == RefType.METHOD
    assert refs[0].class_name == "MyClass"
    assert refs[0].member_name == "method"
    assert refs[0].line_number == 1


def test_ignores_code_blocks():
    text = textwrap.dedent("""\
    This mentions `Real.method()`.

    ```python
    from foo import Phantom
    `FakeClass.ignored()`
    ```

    And also `AnotherReal.method()`.
    """)
    refs = extract_api_references(text)
    names = [r.reference for r in refs]

    assert "Real.method()" in names
    assert "AnotherReal.method()" in names
    assert not any("Fake" in n for n in names)


def test_scan_codebase_finds_classes(tmp_path):
    module = tmp_path / "module.py"
    module.write_text(textwrap.dedent("""\
        class Foo:
            def bar(self):
                pass

            @property
            def baz(self):
                return 1
        """))

    index = scan_codebase(str(tmp_path))

    assert "Foo" in index.classes
    assert "bar" in index.classes["Foo"].methods
    assert "baz" in index.classes["Foo"].properties
    assert "module.py" in index.files


def test_detects_phantom_reference(tmp_path):
    module = tmp_path / "m.py"
    module.write_text(textwrap.dedent("""\
        class Real:
            def alive(self):
                pass
        """))

    index = scan_codebase(str(tmp_path))

    phantom_ref = APIRef(
        reference="Phantom.method()",
        ref_type=RefType.METHOD,
        line_number=1,
        context="",
        class_name="Phantom",
        member_name="method",
    )
    result = verify_ref(phantom_ref, index)

    assert result.status == "phantom"
    assert "Phantom" in result.message
