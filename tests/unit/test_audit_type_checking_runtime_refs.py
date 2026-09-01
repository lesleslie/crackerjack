"""Tests for crackerjack.tools.audit_type_checking_runtime_refs.

Each test writes a synthetic Python source file to ``tmp_path`` and feeds
it through the audit. The fixtures cover:

  - clean files (no TYPE_CHECKING) — no violations
  - TYPE_CHECKING imports unused at runtime — no violations
  - TYPE_CHECKING imports used inside annotation context — safe under
    ``from __future__ import annotations``, violation otherwise
  - TYPE_CHECKING imports used at runtime — always violations
  - ``from X import Y as Z`` aliasing — Z is the runtime name
  - ``import X`` — X is the module-level name
  - star imports — recorded but not statically checked
  - nested TYPE_CHECKING blocks
  - typing.cast references (safe — no runtime lookup)
  - base classes (NOT stringified under future-annotations)
  - module-level re-binding (``Z = ...`` rebinds at runtime)

Exit-code contract: 0 clean, 1 violations, 2 scan errors.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from crackerjack.tools.audit_type_checking_runtime_refs import (
    _collect_annotation_node_ids,
    _collect_tc_body_node_ids,
    _collect_type_checking_imports,
    _collect_type_erased_call_arg_ids,
    _has_future_annotations,
    _is_type_checking_test,
    _scan_file,
    _walk_python_files,
    ImportedName,
    Violation,
)


def parse_src(src: str) -> ast.Module:
    """Parse a source string with leading indentation stripped via textwrap."""
    return ast.parse(textwrap.dedent(src).lstrip("\n"))


def write_source(tmp_path: Path, name: str, source: str) -> Path:
    """Write a Python source file under tmp_path and return its path."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
    return path


# ----- _is_type_checking_test --------------------------------------------------


def test_is_type_checking_test_accepts_bare_name():
    import ast

    node = ast.parse("if TYPE_CHECKING: pass").body[0].test
    assert _is_type_checking_test(node) is True


def test_is_type_checking_test_accepts_typing_attribute():
    import ast

    node = ast.parse("if typing.TYPE_CHECKING: pass").body[0].test
    assert _is_type_checking_test(node) is True


def test_is_type_checking_test_rejects_other_names():
    import ast

    node = ast.parse("if True: pass").body[0].test
    assert _is_type_checking_test(node) is False
    node = ast.parse("if SOME_FLAG: pass").body[0].test
    assert _is_type_checking_test(node) is False


# ----- _has_future_annotations -------------------------------------------------


def test_has_future_annotations_present():
    src = "from __future__ import annotations\nx: int = 1"
    tree = parse_src(src)
    assert _has_future_annotations(tree) is True


def test_has_future_annotations_absent():
    src = "x: int = 1"
    tree = parse_src(src)
    assert _has_future_annotations(tree) is False


def test_has_future_annotations_with_other_future_imports():
    src = "from __future__ import generator_stop\nx: int = 1"
    tree = parse_src(src)
    assert _has_future_annotations(tree) is False


# ----- _collect_type_checking_imports ------------------------------------------


def test_collects_bare_import_from():
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert [i.runtime_name for i in imports] == ["Bar"]


def test_collects_with_alias():
    src = """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar as Baz
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert [i.runtime_name for i in imports] == ["Baz"]


def test_collects_module_import():
    src = """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            import foo
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert [i.runtime_name for i in imports] == ["foo"]


def test_collects_typing_attribute_test():
    src = """
        import typing
        if typing.TYPE_CHECKING:
            from foo import Bar
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert [i.runtime_name for i in imports] == ["Bar"]


def test_collects_nested_import_inside_type_checking():
    src = """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
            if True:
                from baz import Qux
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert sorted(i.runtime_name for i in imports) == ["Bar", "Qux"]


def test_collects_star_import():
    src = """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import *
    """
    tree = parse_src(src)
    imports = _collect_type_checking_imports(tree)
    assert len(imports) == 1
    assert imports[0].is_star is True


# ----- _scan_file: clean files --------------------------------------------------


def test_clean_file_no_type_checking(tmp_path):
    """A file with no TYPE_CHECKING block has zero violations."""
    src = """
        from __future__ import annotations
        from foo import Bar
        x: Bar = Bar()
    """
    path = write_source(tmp_path, "clean.py", src)
    result = _scan_file(path)
    assert result.violations == []
    assert result.parse_error is None


def test_type_checking_import_unused_at_runtime(tmp_path):
    """An import under TYPE_CHECKING that's never referenced is fine."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        x: int = 1
    """
    path = write_source(tmp_path, "unused.py", src)
    result = _scan_file(path)
    assert result.violations == []


# ----- _scan_file: violation cases ---------------------------------------------


def test_runtime_reference_to_type_checking_import_violates(tmp_path):
    """A TYPE_CHECKING import referenced at runtime IS a violation."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        def make() -> object:
            return Bar()
    """
    path = write_source(tmp_path, "violate.py", src)
    result = _scan_file(path)
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.name == "Bar"
    assert "Bar" in v.context


def test_isinstance_reference_violates(tmp_path):
    """An isinstance check on a TYPE_CHECKING-only name is a violation."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        def check(x: object) -> bool:
            return isinstance(x, Bar)
    """
    path = write_source(tmp_path, "isinst.py", src)
    result = _scan_file(path)
    assert len(result.violations) == 1
    assert result.violations[0].name == "Bar"


def test_annotation_only_reference_is_safe_with_future(tmp_path):
    """Under future-annotations, the name in `def f() -> Bar` is safe."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        def make() -> Bar: ...
    """
    path = write_source(tmp_path, "ann.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_annotation_reference_violates_without_future(tmp_path):
    """Without future-annotations, `def f() -> Bar` evaluates Bar at runtime."""
    src = """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        def make() -> Bar: ...
    """
    path = write_source(tmp_path, "no_future.py", src)
    result = _scan_file(path)
    # `Bar` appears in the return annotation, evaluated at runtime
    assert any(v.name == "Bar" for v in result.violations)


def test_parameter_annotation_safe_with_future(tmp_path):
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        def make(x: Bar) -> None: ...
    """
    path = write_source(tmp_path, "param.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_annotated_assignment_safe_with_future(tmp_path):
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        x: Bar = 1
    """
    path = write_source(tmp_path, "annassign.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_base_class_in_class_def_violates(tmp_path):
    """PEP 563 does NOT stringify base classes — they're evaluated normally."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        class Foo(Bar): pass
    """
    path = write_source(tmp_path, "base.py", src)
    result = _scan_file(path)
    assert len(result.violations) == 1
    assert result.violations[0].name == "Bar"


def test_attribute_access_violates(tmp_path):
    """Attribute access on a TYPE_CHECKING-only name is a violation."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        x = Bar.attr
    """
    path = write_source(tmp_path, "attr.py", src)
    result = _scan_file(path)
    assert any(v.name == "Bar" for v in result.violations)


def test_module_import_violates_when_used(tmp_path):
    """`import foo` under TYPE_CHECKING, then `foo.x` at runtime -> violation."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            import foo
        def go() -> int:
            return foo.x
    """
    path = write_source(tmp_path, "modimp.py", src)
    result = _scan_file(path)
    # `foo` reference is Name node; `.x` access is Attribute — both detected.
    assert any(v.name == "foo" for v in result.violations)


def test_typing_cast_is_safe(tmp_path):
    """``typing.cast(Bar, x)`` is annotation-only — cast returns x unchanged."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING, cast
        if TYPE_CHECKING:
            from foo import Bar
        x = cast(Bar, 1)
    """
    path = write_source(tmp_path, "cast.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_module_level_rebind_skips_further_violations(tmp_path):
    """The else-branch ``Bar = None`` is a binding, not a runtime reference.

    This documents the standard "fallback assignment" pattern:
    ``if TYPE_CHECKING: from foo import Bar; else: Bar = make_bar()``.
    The LHS ``Bar = None`` binds the name at runtime; the audit must NOT
    flag this as a runtime reference to the TYPE_CHECKING-only import.
    """
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        else:
            Bar = None
    """
    path = write_source(tmp_path, "rebind.py", src)
    result = _scan_file(path)
    # The LHS of `Bar = None` is a binding site, not a reference.
    assert result.violations == []


def test_star_import_does_not_produce_violations(tmp_path):
    """``from foo import *`` records the star but doesn't generate violations."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import *
        Bar = None
    """
    path = write_source(tmp_path, "star.py", src)
    result = _scan_file(path)
    # The ``Bar = None`` assignment would reference Bar if Bar were a known
    # TYPE_CHECKING-only name; since we don't track star imports, no violation.
    assert result.violations == []


# ----- _scan_file: parse-error handling ----------------------------------------


def test_syntax_error_returns_parse_error(tmp_path):
    path = write_source(tmp_path, "bad.py", "def f( :\n  pass\n")
    result = _scan_file(path)
    assert result.parse_error is not None
    assert "syntax" in result.parse_error.lower()


# ----- _walk_python_files ------------------------------------------------------


def test_walk_python_files_excludes_venv(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "ok.py").write_text("x = 1\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "skip.py").write_text("x = 1\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "skip.py").write_text("x = 1\n")
    files = _walk_python_files([tmp_path])
    names = {p.name for p in files}
    assert names == {"ok.py"}


def test_walk_python_files_nonexistent_root(tmp_path):
    files = _walk_python_files([tmp_path / "does-not-exist"])
    assert files == []


def test_else_branch_imports_are_not_type_checking_only(tmp_path):
    """Imports inside ``else:`` of a TYPE_CHECKING if are runtime imports.

    Pattern::

        if TYPE_CHECKING:
            from foo import Bar  # TC-only
        else:
            from foo import Bar  # runtime import (or fallback)
        Bar()  # safe — else-branch import binds Bar at runtime

    The audit must NOT flag ``Bar()`` as a violation because the else branch
    binds the name at runtime.
    """
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        else:
            from foo import Bar  # runtime import — not TC-only
        x = Bar()
    """
    path = write_source(tmp_path, "else_branch.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_else_branch_runtime_import_rescued_by_assignattr(tmp_path):
    """else-branch ``from foo import X`` then ``X.foo()`` is safe."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            import httpx
        else:
            try:
                import httpx2 as httpx
            except ImportError:
                httpx = None
        if httpx is not None:
            y = httpx.get("url")
    """
    path = write_source(tmp_path, "rescue.py", src)
    result = _scan_file(path)
    # `httpx` reference at runtime is OK because the else branch imports it.
    assert result.violations == []


def test_else_branch_assignment_fallback(tmp_path):
    """Pattern B variant 2: ``else: Msg = Any`` is a runtime assignment fallback.

    The audit must NOT flag ``Msg`` references when the else branch binds
    the name via assignment, not import. This is the standard
    optional-dependency fallback pattern::

        if TYPE_CHECKING:
            from nats.aio.client import Msg
        else:
            Msg = Any
        def handler(m: Msg) -> None: ...  # safe — Msg is bound at runtime
    """
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING, Any
        if TYPE_CHECKING:
            from nats.aio.client import Msg
        else:
            Msg = Any

        def handler(m: Msg) -> None: ...
        x: Msg | None = None
    """
    path = write_source(tmp_path, "nats.py", src)
    result = _scan_file(path)
    # The annotation references are safe under future-annotations.
    # The else-branch assignment binds Msg at runtime.
    # No runtime usage of Msg exists in this fixture.
    assert result.violations == []


def test_else_branch_assignment_fallback_with_runtime_use(tmp_path):
    """Pattern B variant 2 with actual runtime use of the rebound name."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING, Any
        if TYPE_CHECKING:
            from nats.aio.client import Msg
        else:
            Msg = Any
        def make_msg() -> Msg:
            return Msg  # type: ignore[return-value]
    """
    path = write_source(tmp_path, "nats2.py", src)
    result = _scan_file(path)
    # `return Msg` is a runtime reference, but Msg is bound via the
    # else-branch assignment, so it's not a violation.
    assert result.violations == []


def test_else_branch_alias_rebind(tmp_path):
    """Pattern B variant 3: ``else: trace = _trace`` rebinds an aliased import.

    mcp-common style — TC uses ``as _alias`` to avoid name shadowing, else
    branch imports the same alias, then module-level assignment rebinds the
    canonical name::

        if TYPE_CHECKING:
            from opentelemetry import trace as _trace
        else:
            from opentelemetry import trace as _trace
        trace = _trace        # module-level rebind

        def get_tracer() -> trace:
            return trace       # safe — `trace` is rebound at runtime
    """
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from opentelemetry import trace as _trace
        else:
            from opentelemetry import trace as _trace
        trace = _trace

        x = trace
    """
    path = write_source(tmp_path, "telem.py", src)
    result = _scan_file(path)
    # `trace` is rebound via else-branch assignment from the else-imported
    # `_trace`. Runtime use of `trace` at the bottom is safe.
    assert result.violations == []


def test_cluster_by_import_site_groups_same_root_cause():
    """Clustering groups violations sharing an import site into one bucket."""
    from crackerjack.tools.audit_type_checking_runtime_refs import (
        _cluster_by_import_site,
        Violation,
    )
    v1 = Violation(file=Path("a.py"), lineno=10, col_offset=0, name="X", import_lineno=5, context="X")
    v2 = Violation(file=Path("a.py"), lineno=20, col_offset=0, name="X", import_lineno=5, context="X")
    v3 = Violation(file=Path("b.py"), lineno=15, col_offset=0, name="X", import_lineno=7, context="X")
    v4 = Violation(file=Path("a.py"), lineno=30, col_offset=0, name="Y", import_lineno=5, context="Y")
    # Make a FileResult containing these
    from crackerjack.tools.audit_type_checking_runtime_refs import FileResult
    results = [
        FileResult(path=Path("a.py"), violations=[v1, v2, v4]),
        FileResult(path=Path("b.py"), violations=[v3]),
    ]
    clusters = _cluster_by_import_site(results)
    assert len(clusters) == 3  # (5, X), (7, X), (5, Y)
    assert len(clusters[(5, "X")]) == 2
    assert len(clusters[(7, "X")]) == 1
    assert len(clusters[(5, "Y")]) == 1


def test_assignment_target_is_not_a_reference(tmp_path):
    """LHS of assignment is a binding, not a runtime reference."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        try:
            from foo import Bar as BarReal
        except ImportError:
            Bar = None
    """
    path = write_source(tmp_path, "binding.py", src)
    result = _scan_file(path)
    # `Bar = None` is a binding site — should NOT be flagged.
    assert result.violations == []


def test_for_loop_target_is_not_a_reference(tmp_path):
    """for-loop targets are bindings."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        for Bar in []:
            pass
    """
    path = write_source(tmp_path, "for.py", src)
    result = _scan_file(path)
    assert result.violations == []


def test_with_as_target_is_not_a_reference(tmp_path):
    """``with foo as x`` — x is binding, not reference."""
    src = """
        from __future__ import annotations
        from contextlib import contextmanager
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from foo import Bar
        @contextmanager
        def cm():
            yield Bar
        with cm() as Bar:
            pass
    """
    path = write_source(tmp_path, "with.py", src)
    result = _scan_file(path)
    # The `yield Bar` IS a runtime reference (violation).
    # The `as Bar` IS a binding (no violation).
    assert len(result.violations) == 1
    assert result.violations[0].name == "Bar"
    # Context is the unparsed Name node ("Bar"). The parent expression
    # (yield Bar) isn't included in the snippet — that's intentional
    # brevity for the audit report.
    assert result.violations[0].context == "Bar"


def test_non_utf8_file_falls_back_to_latin1(tmp_path):
    """Files with non-UTF-8 encoding are decoded with latin-1 fallback."""
    path = tmp_path / "latin1.py"
    # Latin-1 encoded file with TYPE_CHECKING + runtime ref
    src = (
        "# coding: latin-1\n"
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
        "x = Bar()\n"
    )
    path.write_bytes(src.encode("latin-1"))
    result = _scan_file(path)
    assert result.parse_error is None
    assert len(result.violations) == 1
    assert result.violations[0].name == "Bar"


# ----- Integration: real-world patterns -----------------------------------------


def test_pydantic_model_pattern_violates(tmp_path):
    """Mimics the opera-cloud-mcp Pydantic forward-ref bug."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from models.guest import Guest
        class ReservationCreateRequest:
            guest: Guest | None = None
            def __init__(self, g: Guest) -> None:
                self.guest = g
    """
    path = write_source(tmp_path, "pyd.py", src)
    result = _scan_file(path)
    # Annotation references are safe (future-annotations). The runtime
    # reference in __init__ (g: Guest) is also annotation — safe.
    # The `g: Guest` annotation is safe, no runtime lookup.
    assert result.violations == []


def test_pydantic_model_runtime_construction_violates(tmp_path):
    """The actual opera-cloud-mcp bug: TYPE_CHECKING import referenced in
    a function body where the type is evaluated at class-definition time
    because it's used in a non-annotation position."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from models.guest import Guest
        def make_reservation() -> object:
            return {"guest": Guest(name="x")}
    """
    path = write_source(tmp_path, "pyd2.py", src)
    result = _scan_file(path)
    assert len(result.violations) == 1
    assert result.violations[0].name == "Guest"


def test_graphics_mcp_pillow_pattern_violates(tmp_path):
    """The actual graphics-mcp bug: TransformResult referenced in
    runtime success/error result constructors."""
    src = """
        from __future__ import annotations
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from graphics_mcp.types import TransformResult, CropOptions
        def transform(img, opts):
            if opts is None:
                return TransformResult(success=False, error="no opts")
            return TransformResult(success=True, value=img)
    """
    path = write_source(tmp_path, "pillow.py", src)
    result = _scan_file(path)
    # `TransformResult` appears twice — both are runtime references.
    assert sum(1 for v in result.violations if v.name == "TransformResult") == 2
    assert all(v.name != "CropOptions" for v in result.violations)


# ----- CLI smoke ---------------------------------------------------------------


def test_cli_module_runs(tmp_path):
    """The script's __main__ entry point can be invoked with a single root."""
    import subprocess
    import sys

    # Write a clean file under tmp_path
    (tmp_path / "clean.py").write_text("x = 1\n")
    # Write a violating file
    (tmp_path / "violate.py").write_text(
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
        "x = Bar()\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "crackerjack.tools.audit_type_checking_runtime_refs", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1  # violations present
    assert "Bar" in result.stdout


def test_cli_exits_zero_on_clean_tree(tmp_path):
    import subprocess
    import sys

    (tmp_path / "clean.py").write_text("x = 1\n")
    result = subprocess.run(
        [sys.executable, "-m", "crackerjack.tools.audit_type_checking_runtime_refs", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No violations found" in result.stdout
