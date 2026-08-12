"""Deterministic AST-based test-scaffolding fixer.

Extracted from ``crackerjack.agents.test_creation_agent.TestCreationAgent``
and its three delegate helper classes under
``crackerjack.agents.helpers.test_creation``: ``TestASTAnalyzer``,
``TestTemplateGenerator``, and ``TestCoverageAnalyzer``. All three helper
classes stored ``context: AgentContext`` and used it only for
``project_path``, ``get_file_content``, and ``write_file_content`` -- no
``SubAgent``/coordinator dependency, no LLM calls, just ``ast.parse``/
``ast.walk`` over ``FunctionDef``/``AsyncFunctionDef`` nodes plus
deterministic string-template generation. Flattened into module-level
functions with ``project_path: Path`` threaded explicitly wherever
``self.context.project_path`` was load-bearing (same treatment as Task 7's
``_find_best_link_target``), matching the precedent set by Task 4 (
``crackerjack/fixers/refactoring.py`` absorbed its 3 helper classes
wholesale rather than just ``refactoring_agent.py``'s thin wrappers).

What was intentionally dropped versus the original ``TestCreationAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__``, ``can_handle``
  and its confidence-scoring helpers (``_check_test_organization_confidence``,
  ``_check_perfect_test_creation_matches``, ``_check_good_test_creation_matches``,
  ``_check_file_path_test_indicators``, ``_indicates_untested_functions``),
  ``get_supported_types``, ``agent_registry.register(...)`` -- these only
  ever decided *whether* and *how confidently* this fixer should run for a
  given ``Issue``; that routing job belongs to whatever calls into this
  module now, not to the module itself.
- A ten-method-deep pure pass-through chain on the agent
  (``_apply_test_creation_fixes`` -> ``_apply_all_test_creation_fixes`` ->
  ``_apply_all_fix_types`` -> ``_apply_sequential_fixes`` ->
  ``_apply_all_fix_types_sequentially`` -> ``_apply_all_fix_types_in_sequence``
  -> ``_apply_fix_types_in_defined_order``, plus the near-duplicate
  ``_apply_coverage_fixes``/``_apply_file_fixes``/``_apply_function_fixes``
  aliases of ``_apply_coverage_based_fixes_sequentially``/
  ``_apply_file_specific_fixes_sequentially``/
  ``_apply_function_specific_fixes_sequentially``) -- every one of these
  methods just forwards its arguments to the next with zero branching
  logic. Collapsed below into ``_apply_test_creation_fixes`` calling the
  three real fix-application steps directly, in the same order, feeding
  ``create_tests_for_issue``.
- Similarly, ``TestTemplateGenerator._generate_all_test_types`` chained
  through ``_generate_function_tests_content``/``_generate_class_tests_content``/
  ``_generate_integration_tests_content``, each a single-line forward to the
  real ``_generate_enhanced_function_tests``/``_generate_enhanced_class_tests``/
  ``_generate_integration_tests``. Collapsed the same way.
- ``self.log(...)``/``self._log(...)`` calls throughout -- ``SubAgent.log``
  is a no-op ``pass`` on the base class, and ``TestASTAnalyzer``/
  ``TestCoverageAnalyzer`` each define their *own* local no-op ``_log``
  stub too (``TestTemplateGenerator`` has no logging at all). Dropped along
  with the rest of the coordinator plumbing (same treatment as
  ``crackerjack/fixers/security.py``).
- ``AgentContext``-specific file I/O (``get_file_content``'s/
  ``write_file_content``'s path-traversal checks, ``write_file_content``'s
  ``wrap_long_lines`` post-processing which itself imports from the
  to-be-removed ``crackerjack.ai_fix`` package, and ``.py`` syntax
  revalidation) -- replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below. Real file I/O is still performed;
  only the framework wrapper is gone.

Duplication preserved verbatim (not merged away), per CLAUDE.md Rule 7
("preserve functional requirements... fix the technical issue, not the
requirements"):

- ``TestCreationAgent`` and ``TestCoverageAnalyzer`` each independently
  define a method named ``_identify_coverage_gaps``/
  ``_analyze_existing_test_coverage``/``_find_untested_functions_in_file`` --
  similarly-named but *not* identical implementations. Only the
  ``TestCoverageAnalyzer`` versions (kept below as ``_identify_coverage_gaps``,
  ``_analyze_existing_test_coverage``, ``_find_untested_functions_in_file``)
  are reachable from the live ``analyze_and_fix`` pipeline (via
  ``analyze_coverage``/``find_untested_functions``); the ``TestCreationAgent``
  versions (kept below as ``identify_coverage_gaps``,
  ``analyze_existing_test_coverage``, ``find_untested_functions_in_file`` --
  no leading underscore) were never called from anywhere else in the
  original agent, only exercised directly by unit tests. Both variants are
  ported under these distinct names since they are behaviorally different:
  notably, ``TestCoverageAnalyzer._analyze_existing_test_coverage`` sets
  ``coverage_info["has_gaps"]`` to the *list* ``missing_types`` (truthy/
  falsy, not a real ``bool``), while ``TestCreationAgent``'s version
  correctly computes ``len(missing_types) > 0``. Preserved verbatim, not
  fixed.
- Likewise, ``TestCoverageAnalyzer._analyze_module_priority`` (kept below
  as ``_analyze_module_priority``, the version actually used by
  ``_find_uncovered_modules_enhanced``) computes ``public_function_count``
  from the functions list returned by ``extract_functions_from_file``
  (which already excludes leading-underscore and ``test_``-prefixed
  names). ``TestCreationAgent``'s own ``_analyze_module_priority`` (kept
  below as ``analyze_module_priority``, no leading underscore) calls that,
  then *overwrites* ``public_function_count`` with a second, independent
  computation: a fresh ``ast.parse``/``ast.walk`` over the module source,
  counting top-level (``col_offset == 0``) ``FunctionDef``/
  ``AsyncFunctionDef`` nodes not starting with ``_``. Like the coverage-gap
  methods above, this override is never invoked from the live pipeline --
  ``_find_uncovered_modules_enhanced`` always calls the base
  ``_analyze_module_priority`` -- only from direct calls/tests.
- ``TestASTAnalyzer.get_module_import_path`` and
  ``TestTemplateGenerator._get_module_import_path`` were byte-identical;
  likewise ``TestTemplateGenerator._categorize_module`` and
  ``TestCoverageAnalyzer._categorize_module``. Consolidated into one
  shared ``_get_module_import_path``/``_categorize_module`` function each
  here -- a no-op structural dedup, not a behavior change (same treatment
  as ``crackerjack/fixers/security.py``'s consolidation of repeated
  ``SAFE_PATTERNS`` imports). Note ``TestASTAnalyzer.get_module_import_path``
  and ``get_relative_module_path`` were never actually called anywhere in
  the original agent (dead surface on that helper); ported anyway since
  they are real, correct, and cheap.
- ``TestCreationAgent._create_test_creation_result`` has a type-defying
  quirk, preserved verbatim below in ``_create_test_creation_result``:
  ``success = fixes_applied`` assigns the *list* itself (not
  ``bool(fixes_applied)``) to the variable subsequently passed as
  ``FixResult(success=success, ...)`` (a field typed ``bool``) and to
  ``_calculate_confidence``/``_generate_recommendations``. The original
  marks both call sites with ``# type: ignore``, i.e. the author knew this
  doesn't really type-check. At runtime this works only because Python
  dataclasses don't validate field types and list truthiness matches bool
  semantics in the ``if not success`` / ``if success`` checks downstream --
  but ``FixResult.success`` ends up holding a ``list[str]``, not a
  ``bool``, whenever fixes were applied.

Preserved quirks (not fixed), per CLAUDE.md Rule 7:

1. ``generate_test_file_path`` has a side effect: it creates the project's
   ``tests/`` directory (``tests_dir.mkdir(exist_ok=True)``) merely as a
   side effect of computing a path, even when just checking whether a test
   file exists (e.g. via ``function_has_test``/``has_corresponding_test``).
2. ``_run_coverage_command`` (renamed ``_run_coverage_command_stub`` here)
   is a dead stub: it never runs any actual coverage command and always
   returns ``(1, "", "Coverage command not available in helper")``. Every
   call site through ``analyze_coverage`` therefore always takes the
   ``_process_coverage_results_enhanced`` fallback path (heuristic
   file-count-ratio estimation via ``_estimate_current_coverage``) rather
   than reading real coverage tool output, unless a ``coverage.json``/
   ``.coverage`` file already exists on disk.
3. The header text built by ``_generate_enhanced_test_file_header`` opens
   with a literal triple-double-quote immediately followed by the import
   lines, and a second, indented triple-double-quote appears later on the
   "Tests for ..." line -- the triple-quote delimiters do not line up the
   way a real module docstring would need to. Preserved verbatim; not our
   job to make the generated scaffold syntactically valid Python.
"""

from __future__ import annotations

import ast
import asyncio
import json
import operator
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from crackerjack.models.issues import FixResult, Issue

# ---------------------------------------------------------------------------
# File I/O (replaces AgentContext.get_file_content/write_file_content)
# ---------------------------------------------------------------------------


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (Exception, OSError):
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# AST extraction (from TestASTAnalyzer)
# ---------------------------------------------------------------------------


async def extract_functions_from_file(file_path: Path) -> list[dict[str, Any]]:
    functions: list[dict[str, Any]] = []

    with suppress(Exception):
        content = _read_file(file_path)
        if not content:
            return functions

        tree = ast.parse(content)
        functions = _parse_function_nodes(tree)

    return functions


def _parse_function_nodes(tree: ast.AST) -> list[dict[str, Any]]:
    functions: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.FunctionDef | ast.AsyncFunctionDef,
        ) and _is_valid_function_node(node):
            function_info = _create_function_info(node)

            function_info["is_async"] = isinstance(node, ast.AsyncFunctionDef)
            functions.append(function_info)

    return functions


def _is_valid_function_node(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return not node.name.startswith(("_", "test_"))


def _create_function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:
    return {
        "name": node.name,
        "line": node.lineno,
        "signature": _get_function_signature(node),
        "args": [arg.arg for arg in node.args.args],
        "returns": _get_return_annotation(node),
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "docstring": ast.get_docstring(node) or "",
    }


async def extract_classes_from_file(file_path: Path) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []

    with suppress(Exception):
        content = _read_file(file_path)
        if not content:
            return classes

        tree = ast.parse(content)
        classes = _process_ast_nodes_for_classes(tree)

    return classes


def _process_ast_nodes_for_classes(tree: ast.AST) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _should_include_class(node):
            class_info = _create_class_info(node)
            classes.append(class_info)

    return classes


def _should_include_class(node: ast.ClassDef) -> bool:
    return not node.name.startswith("_")


def _create_class_info(node: ast.ClassDef) -> dict[str, Any]:
    methods = _extract_public_methods_from_class(node)
    return {"name": node.name, "line": node.lineno, "methods": methods}


def _extract_public_methods_from_class(node: ast.ClassDef) -> list[str]:
    return [
        item.name
        for item in node.body
        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")
    ]


def _get_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    args = [arg.arg for arg in node.args.args]
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({', '.join(args)})"


def _get_return_annotation(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    if node.returns:
        return ast.unparse(node.returns) if (hasattr(ast, "unparse")) else "Any"
    return "Any"


async def function_has_test(
    func_info: dict[str, Any],
    file_path: Path,
    project_path: Path,
) -> bool:
    test_file_path = await generate_test_file_path(file_path, project_path)

    if not test_file_path.exists():
        return False

    test_content = _read_file(test_file_path)
    if not test_content:
        return False

    test_patterns = [
        f"test_{func_info['name']}",
        f"test_{func_info['name']}_",
        f"def test_{func_info['name']}",
    ]

    return any(pattern in test_content for pattern in test_patterns)


async def generate_test_file_path(source_file: Path, project_path: Path) -> Path:
    tests_dir = project_path / "tests"
    tests_dir.mkdir(exist_ok=True)

    relative_path = source_file.relative_to(project_path / "crackerjack")
    test_name = f"test_{relative_path.stem}.py"

    return tests_dir / test_name


def _get_module_import_path(file_path: Path, project_path: Path) -> str:
    try:
        relative_path = file_path.relative_to(project_path)
        parts = (*relative_path.parts[:-1], relative_path.stem)
        return ".".join(parts)
    except (Exception, ValueError):
        return file_path.stem


def should_skip_module_for_coverage(py_file: Path) -> bool:
    return py_file.name.startswith("test_") or py_file.name == "__init__.py"


def should_skip_file_for_testing(py_file: Path) -> bool:
    return py_file.name.startswith("test_")


def has_corresponding_test(file_path: str, project_path: Path) -> bool:
    path = Path(file_path)

    test_patterns = [
        f"test_{path.stem}.py",
        f"{path.stem}_test.py",
        f"test_{path.stem}_*.py",
    ]

    tests_dir = project_path / "tests"
    if tests_dir.exists():
        for pattern in test_patterns:
            if list(tests_dir.glob(pattern)):
                return True

    return False


def get_relative_module_path(py_file: Path, project_path: Path) -> str:
    return str(py_file.relative_to(project_path))


# ---------------------------------------------------------------------------
# Test-content template generation (from TestTemplateGenerator)
# ---------------------------------------------------------------------------


async def generate_test_content(
    module_file: Path,
    functions: list[dict[str, Any]],
    classes: list[dict[str, Any]],
    project_path: Path,
) -> str:
    test_params = _prepare_test_generation_params(module_file, project_path)
    return await _generate_all_test_types(test_params, functions, classes)


async def generate_comprehensive_test_content(
    test_params: dict[str, Any],
    functions: list[dict[str, Any]],
    classes: list[dict[str, Any]],
) -> str:
    return await _generate_all_test_types(test_params, functions, classes)


def _prepare_test_generation_params(
    module_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    module_name = _get_module_import_path(module_file, project_path)
    module_category = _categorize_module(
        str(module_file.relative_to(project_path)),
    )
    return {
        "module_name": module_name,
        "module_file": module_file,
        "module_category": module_category,
    }


async def _generate_all_test_types(
    test_params: dict[str, Any],
    functions: list[dict[str, Any]],
    classes: list[dict[str, Any]],
) -> str:
    base_content = _generate_enhanced_test_file_header(
        test_params["module_name"],
        test_params["module_file"],
        test_params["module_category"],
    )

    function_tests = await _generate_enhanced_function_tests(
        functions,
        test_params["module_category"],
    )
    class_tests = await _generate_enhanced_class_tests(
        classes,
        test_params["module_category"],
    )
    integration_tests = await _generate_integration_tests(
        test_params["module_file"],
        functions,
        classes,
        test_params["module_category"],
    )

    return base_content + function_tests + class_tests + integration_tests


def _generate_enhanced_test_file_header(
    module_name: str,
    module_file: Path,
    module_category: str,
) -> str:
    imports = [
        "import pytest",
        "from pathlib import Path",
        "from unittest.mock import Mock, patch, AsyncMock",
    ]

    if module_category in ("service", "manager", "core"):
        imports.append("import asyncio")

    imports_str = "\n".join(imports)

    try:
        content = _read_file(module_file) or ""
        tree = ast.parse(content)

        importable_items = [
            node.name
            for node in ast.walk(tree)
            if (isinstance(node, ast.ClassDef) and not node.name.startswith("_"))
            or (
                isinstance(
                    node,
                    ast.FunctionDef | ast.AsyncFunctionDef,
                )
                and not node.name.startswith("_")
            )
        ]

        if importable_items:
            specific_imports = (
                f"from {module_name} import {', '.join(importable_items[:10])}"
            )
        else:
            specific_imports = f"import {module_name}"

    except Exception:
        specific_imports = f"import {module_name}"

    class_name = f"Test{module_file.stem.replace('_', '').title()}"

    return (
        f'"""{imports_str}\n'
        f"{specific_imports}\n"
        "\n"
        "\n"
        f"class {class_name}:\n"
        f' """Tests for {module_name}.\n'
        "\n"
        f" This module contains comprehensive tests for {module_name}\n"
        " including:\n"
        " - Basic functionality tests\n"
        " - Edge case validation\n"
        " - Error handling verification\n"
        " - Integration testing\n"
        " - Performance validation (where applicable)\n"
        ' """\n'
        "\n"
        " def test_module_imports_successfully(self):\n"
        ' """Test that the module can be imported without errors."""\n'
        f" import {module_name}\n"
        f" assert {module_name} is not None\n"
    )


async def generate_function_test(func_info: dict[str, Any]) -> str:
    func_name = func_info["name"]
    args = func_info.get("args", [])

    return f"""def test_{func_name}_basic(self):
    \"\"\"Test basic functionality of {func_name}.\"\"\"
    try:
        result = {func_name}({_generate_default_args(args)})
        assert result is not None or result is None
    except TypeError:
        pytest.skip(
            "Function requires specific arguments - manual implementation needed"
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in {func_name}: {{e}}")"""


async def _generate_enhanced_function_tests(
    functions: list[dict[str, Any]],
    module_category: str,
) -> str:
    if not functions:
        return ""

    test_methods = []
    for func in functions:
        func_tests = await _generate_all_tests_for_function(func, module_category)
        test_methods.extend(func_tests)

    return "\n".join(test_methods)


async def _generate_all_tests_for_function(
    func: dict[str, Any],
    module_category: str,
) -> list[str]:
    func_tests = []

    basic_test = await _generate_basic_function_test(func, module_category)
    func_tests.append(basic_test)

    additional_tests = await _generate_conditional_tests_for_function(
        func,
        module_category,
    )
    func_tests.extend(additional_tests)

    return func_tests


async def _generate_conditional_tests_for_function(
    func: dict[str, Any],
    module_category: str,
) -> list[str]:
    tests = []
    args = func.get("args", [])
    func_name = func["name"]

    if _should_generate_parametrized_test(args):
        parametrized_test = await _generate_parametrized_test(func, module_category)
        tests.append(parametrized_test)

    error_test = await _generate_error_handling_test(func, module_category)
    tests.append(error_test)

    if _should_generate_edge_case_test(args, func_name):
        edge_test = await _generate_edge_case_test(func, module_category)
        tests.append(edge_test)

    return tests


def _should_generate_parametrized_test(args: list[str]) -> bool:
    return len(args) > 1


def _should_generate_edge_case_test(args: list[str], func_name: str) -> bool:
    has_multiple_args = len(args) > 2
    is_complex_function = any(
        hint in func_name.lower() for hint in ("process", "validate", "parse", "convert")
    )
    return has_multiple_args or is_complex_function


async def _generate_basic_function_test(
    func: dict[str, Any],
    module_category: str,
) -> str:
    func_name = func["name"]
    args = func.get("args", [])

    template_generator = _get_test_template_generator(module_category)
    return template_generator(func_name, args)


def _get_test_template_generator(
    module_category: str,
) -> Callable[[str, list[str]], str]:
    return {
        "agent": _generate_agent_test_template,
        "service": _generate_async_test_template,
        "manager": _generate_async_test_template,
    }.get(module_category, _generate_default_test_template)


def _generate_agent_test_template(func_name: str, args: list[str]) -> str:
    template = (
        " def test_FUNC_NAME_basic_functionality(self):\n"
        ' """Test basic functionality of FUNC_NAME."""\n'
        "\n"
        "\n"
        " try:\n"
        " result = FUNC_NAME(ARGS)\n"
        " assert result is not None or result is None\n"
        " except (TypeError, NotImplementedError) as e:\n"
        + (
            " pytest.skip('Function FUNC_NAME requires manual "
            "implementation: ' + str(e))\n"
        )
        + " except Exception as e:\n"
        " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
    )

    return template.replace("FUNC_NAME", func_name).replace(
        "ARGS",
        _generate_smart_default_args(args),
    )


def _generate_async_test_template(func_name: str, args: list[str]) -> str:
    template = (
        " @pytest.mark.asyncio\n"
        " async def test_FUNC_NAME_basic_functionality(self):\n"
        ' """Test basic functionality of FUNC_NAME."""\n'
        "\n"
        "\n"
        " try:\n"
        " if asyncio.iscoroutinefunction(FUNC_NAME):\n"
        " result = await FUNC_NAME(ARGS)\n"
        " else:\n"
        " result = FUNC_NAME(ARGS)\n"
        " assert result is not None or result is None\n"
        " except (TypeError, NotImplementedError) as e:\n"
        + (
            " pytest.skip('Function FUNC_NAME requires manual "
            "implementation: ' + str(e))\n"
        )
        + " except Exception as e:\n"
        " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
    )

    return template.replace("FUNC_NAME", func_name).replace(
        "ARGS",
        _generate_smart_default_args(args),
    )


def _generate_default_test_template(func_name: str, args: list[str]) -> str:
    template = (
        " def test_FUNC_NAME_basic_functionality(self):\n"
        ' """Test basic functionality of FUNC_NAME."""\n'
        " try:\n"
        " result = FUNC_NAME(ARGS)\n"
        " assert result is not None or result is None\n"
        " except (TypeError, NotImplementedError) as e:\n"
        + (
            " pytest.skip('Function FUNC_NAME requires manual "
            "implementation: ' + str(e))\n"
        )
        + " except Exception as e:\n"
        " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
    )

    return template.replace("FUNC_NAME", func_name).replace(
        "ARGS",
        _generate_smart_default_args(args),
    )


async def _generate_parametrized_test(
    func: dict[str, Any],
    module_category: str,
) -> str:
    func_name = func["name"]
    args = func.get("args", [])

    test_cases = _generate_test_parameters(args)

    if not test_cases:
        return ""

    parametrize_decorator = f"@pytest.mark.parametrize({test_cases})"

    return (
        f" {parametrize_decorator}\n"
        f" def test_{func_name}_with_parameters(self, "
        f"{', '.join(args) if len(args) <= 5 else 'test_input'}):\n"
        f' """Test {func_name} with various parameter combinations."""\n'
        " try:\n"
        f" if len({args}) <= 5:\n"
        f" result = {func_name}({', '.join(args)})\n"
        " else:\n"
        f" result = {func_name}(**test_input)\n"
        "\n"
        " assert result is not None or result is None\n"
        " except (TypeError, ValueError) as expected_error:\n"
        "\n"
        " pass\n"
        " except Exception as e:\n"
        ' pytest.fail(f"Unexpected error with parameters: {e}")'
    )


async def _generate_error_handling_test(
    func: dict[str, Any],
    module_category: str,
) -> str:
    func_name = func["name"]
    args = func.get("args", [])

    return (
        f" def test_{func_name}_error_handling(self):\n"
        f' """Test {func_name} error handling with invalid inputs."""\n'
        "\n"
        " with pytest.raises((TypeError, ValueError, AttributeError)):\n"
        f" {func_name}({_generate_invalid_args(args)})\n"
        "\n"
        "\n"
        f" if {args}:\n"
        " with pytest.raises((TypeError, ValueError)):\n"
        f" {func_name}("
        f"{_generate_edge_case_args(args, 'empty')})"
    )


async def _generate_edge_case_test(
    func: dict[str, Any],
    module_category: str,
) -> str:
    func_name = func["name"]
    args = func.get("args", [])

    return (
        f" def test_{func_name}_edge_cases(self):\n"
        f' """Test {func_name} with edge case scenarios."""\n'
        "\n"
        " edge_cases = [\n"
        f" {_generate_edge_case_args(args, 'boundary')}, \n"
        f" {_generate_edge_case_args(args, 'extreme')}, \n"
        " ]\n"
        "\n"
        " for edge_case in edge_cases:\n"
        " try:\n"
        f" result = {func_name}(*edge_case)\n"
        "\n"
        " assert result is not None or result is None\n"
        " except (ValueError, TypeError):\n"
        "\n"
        " pass\n"
        " except Exception as e:\n"
        ' pytest.fail(f"Unexpected error with edge case {edge_case}: '
        '{e}")'
    )


def _generate_test_parameters(args: list[str]) -> str:
    if not args or len(args) > 5:
        return ""

    param_names = ", ".join(f'"{arg}"' for arg in args)
    param_values = []

    for i in range(min(3, len(args))):
        test_case = []
        for arg in args:
            if "path" in arg.lower():
                test_case.append(f'Path("test_{i}")')
            elif "str" in arg.lower() or "name" in arg.lower():
                test_case.append(f'"test_{i}"')
            elif "int" in arg.lower() or "count" in arg.lower():
                test_case.append(str(i))
            elif "bool" in arg.lower():
                test_case.append("True" if i % 2 == 0 else "False")
            else:
                test_case.append("None")
        param_values.append(f"({', '.join(test_case)})")

    return f"[{param_names}], [{', '.join(param_values)}]"


def _generate_smart_default_args(args: list[str]) -> str:
    if not args or args == ["self"]:
        return ""

    filtered_args = _filter_args(args)
    if not filtered_args:
        return ""

    placeholders = [_generate_placeholder_for_arg(arg) for arg in filtered_args]
    return ", ".join(placeholders)


def _filter_args(args: list[str]) -> list[str]:
    return [arg for arg in args if arg != "self"]


def _generate_placeholder_for_arg(arg: str) -> str:
    arg_lower = arg.lower()

    if _is_path_arg(arg_lower):
        return 'Path("test_file.txt")'
    if _is_url_arg(arg_lower):
        return '"https: //example.com"'
    if _is_email_arg(arg_lower):
        return '"test@example.com"'
    if _is_id_arg(arg_lower):
        return '"test-id-123"'
    if _is_name_arg(arg_lower):
        return '"test_name"'
    if _is_numeric_arg(arg_lower):
        return "10"
    if _is_boolean_arg(arg_lower):
        return "True"
    if _is_text_arg(arg_lower):
        return '"test data"'
    if _is_list_arg(arg_lower):
        return '["test1", "test2"]'
    if _is_dict_arg(arg_lower):
        return '{"key": "value"}'
    return '"test"'


def _is_path_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("path", "file"))


def _is_url_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("url", "uri"))


def _is_email_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("email", "mail"))


def _is_id_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("id", "uuid"))


def _is_name_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("name", "title"))


def _is_numeric_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("count", "size", "number", "num"))


def _is_boolean_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("enable", "flag", "is_", "has_"))


def _is_text_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("data", "content", "text"))


def _is_list_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("list[t.Any]", "items"))


def _is_dict_arg(arg_lower: str) -> bool:
    return any(term in arg_lower for term in ("dict[str, t.Any]", "config", "options"))


def _generate_invalid_args(args: list[str]) -> str:
    filtered_args = [arg for arg in args if arg != "self"]
    if not filtered_args:
        return ""
    return ", ".join(["None"] * len(filtered_args))


def _generate_edge_case_args(args: list[str], case_type: str) -> str:
    filtered_args = _filter_args(args)
    if not filtered_args:
        return ""

    placeholders = _generate_placeholders_by_case_type(filtered_args, case_type)
    return ", ".join(placeholders)


def _generate_placeholders_by_case_type(
    filtered_args: list[str],
    case_type: str,
) -> list[str]:
    if case_type == "empty":
        return _generate_empty_case_placeholders(filtered_args)
    if case_type == "boundary":
        return _generate_boundary_case_placeholders(filtered_args)

    return _generate_extreme_case_placeholders(filtered_args)


def _generate_empty_case_placeholders(filtered_args: list[str]) -> list[str]:
    placeholders = []
    for arg in filtered_args:
        arg_lower = arg.lower()
        if any(term in arg_lower for term in ("str", "name", "text")):
            placeholders.append('""')
        elif any(term in arg_lower for term in ("list[t.Any]", "items")):
            placeholders.append("[]")
        elif any(term in arg_lower for term in ("dict[str, t.Any]", "config")):
            placeholders.append("{}")
        else:
            placeholders.append("None")
    return placeholders


def _generate_boundary_case_placeholders(filtered_args: list[str]) -> list[str]:
    placeholders = []
    for arg in filtered_args:
        arg_lower = arg.lower()
        if any(term in arg_lower for term in ("count", "size", "number")):
            placeholders.append("0")
        elif any(term in arg_lower for term in ("str", "name")):
            placeholders.append('"x" * 1000')
        else:
            placeholders.append("None")
    return placeholders


def _generate_extreme_case_placeholders(filtered_args: list[str]) -> list[str]:
    placeholders = []
    for arg in filtered_args:
        arg_lower = arg.lower()
        if any(term in arg_lower for term in ("count", "size", "number")):
            placeholders.append("-1")
        else:
            placeholders.append("None")
    return placeholders


async def _generate_enhanced_class_tests(
    classes: list[dict[str, Any]],
    module_category: str,
) -> str:
    if not classes:
        return ""

    test_components = await _generate_all_class_test_components(
        classes,
        module_category,
    )
    return _combine_class_test_elements(
        test_components["fixtures"],
        test_components["test_methods"],
    )


async def _generate_all_class_test_components(
    classes: list[dict[str, Any]],
    module_category: str,
) -> dict[str, list[str]]:
    fixtures = []
    test_methods = []

    for cls in classes:
        class_components = await _generate_single_class_test_components(
            cls,
            module_category,
        )
        fixtures.extend(class_components["fixtures"])
        test_methods.extend(class_components["test_methods"])

    return {"fixtures": fixtures, "test_methods": test_methods}


async def _generate_single_class_test_components(
    cls: dict[str, Any],
    module_category: str,
) -> dict[str, list[str]]:
    fixtures = []
    test_methods = []
    methods = cls.get("methods", [])

    fixture = await _generate_class_fixture(cls, module_category)
    if fixture:
        fixtures.append(fixture)

    core_tests = await _generate_core_class_tests(cls, methods, module_category)
    test_methods.extend(core_tests)

    return {"fixtures": fixtures, "test_methods": test_methods}


async def _generate_core_class_tests(
    cls: dict[str, Any],
    methods: list[str],
    module_category: str,
) -> list[str]:
    test_methods = []

    instantiation_test = await _generate_class_instantiation_test(
        cls,
        module_category,
    )
    test_methods.append(instantiation_test)

    method_tests = await _generate_method_tests(cls, methods[:5], module_category)
    test_methods.extend(method_tests)

    property_test = await _generate_class_property_test(cls, module_category)
    if property_test:
        test_methods.append(property_test)

    return test_methods


async def _generate_method_tests(
    cls: dict[str, Any],
    methods: list[str],
    module_category: str,
) -> list[str]:
    method_tests = []
    for method in methods:
        method_test = await _generate_class_method_test(cls, method, module_category)
        method_tests.append(method_test)
    return method_tests


def _combine_class_test_elements(
    fixtures: list[str],
    test_methods: list[str],
) -> str:
    fixture_section = "\n".join(fixtures) if fixtures else ""
    test_section = "\n".join(test_methods)
    return fixture_section + test_section


async def _generate_class_fixture(
    cls: dict[str, Any],
    module_category: str,
) -> str:
    class_name = cls["name"]

    if module_category in ("service", "manager", "core"):
        fixture_template = (
            " @pytest.fixture\n"
            f" def {class_name.lower()}_instance(self):\n"
            f' """Fixture to create {class_name} instance for testing."""\n'
            "\n"
            " try:\n"
            f" return {class_name}()\n"
            " except TypeError:\n"
            "\n"
            f" with patch.object({class_name}, '__init__', return_value=None):\n"
            f" instance = {class_name}.__new__({class_name})\n"
            " return instance"
        )

    elif module_category == "agent":
        fixture_template = (
            " @pytest.fixture\n"
            f" def {class_name.lower()}_instance(self):\n"
            f' """Fixture to create {class_name} instance for testing."""\n'
            "\n"
            " mock_context = Mock(spec=AgentContext)\n"
            ' mock_context.project_path = Path("/test/project")\n'
            ' mock_context.get_file_content = Mock(return_value="# test content")\n'
            " mock_context.write_file_content = Mock(return_value=True)\n"
            "\n"
            " try:\n"
            f" return {class_name}(mock_context)\n"
            " except Exception:\n"
            ' pytest.skip("Agent requires specific context configuration")'
        )

    else:
        fixture_template = (
            " @pytest.fixture\n"
            f" def {class_name.lower()}_instance(self):\n"
            f' """Fixture to create {class_name} instance for testing."""\n'
            " try:\n"
            f" return {class_name}()\n"
            " except TypeError:\n"
            ' pytest.skip("Class requires specific constructor arguments")'
        )

    return fixture_template


async def _generate_class_instantiation_test(
    class_info: dict[str, Any],
    module_category: str,
) -> str:
    class_name = class_info["name"]

    return (
        f" def test_{class_name.lower()}_instantiation(self, {class_name.lower()}_instance):\n"
        f' """Test successful instantiation of {class_name}."""\n'
        f" assert {class_name.lower()}_instance is not None\n"
        f" assert isinstance({class_name.lower()}_instance, {class_name})\n"
        "\n"
        f" assert hasattr({class_name.lower()}_instance, '__class__')\n"
        f' assert {class_name.lower()}_instance.__class__.__name__ == "{class_name}"'
    )


async def _generate_class_method_test(
    cls: dict[str, Any],
    method_name: str,
    module_category: str,
) -> str:
    class_name = cls["name"]

    if _is_special_agent_method(module_category, method_name):
        return _generate_agent_method_test(class_name, method_name)
    if module_category in ("service", "manager"):
        return _generate_async_method_test(class_name, method_name)
    return _generate_default_method_test(class_name, method_name)


def _is_special_agent_method(module_category: str, method_name: str) -> bool:
    return module_category == "agent" and method_name in (
        "can_handle",
        "analyze_and_fix",
    )


def _generate_agent_method_test(class_name: str, method_name: str) -> str:
    if method_name == "can_handle":
        return _generate_can_handle_test(class_name)
    if method_name == "analyze_and_fix":
        return _generate_analyze_and_fix_test(class_name)
    return _generate_generic_agent_method_test(class_name, method_name)


def _generate_can_handle_test(class_name: str) -> str:
    return (
        " @pytest.mark.asyncio\n"
        f" async def test_{class_name.lower()}_can_handle(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name}.can_handle method."""\n'
        "\n"
        " mock_issue = Mock(spec=Issue)\n"
        " mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
        ' mock_issue.message = "test coverage issue"\n'
        ' mock_issue.file_path = "/test/path.py"\n'
        "\n"
        f" result = await {class_name.lower()}_instance.can_handle(mock_issue)\n"
        " assert isinstance(result, (int, float))\n"
        " assert 0.0 <= result <= 1.0"
    )


def _generate_analyze_and_fix_test(class_name: str) -> str:
    return (
        " @pytest.mark.asyncio\n"
        f" async def test_{class_name.lower()}_analyze_and_fix(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name}.analyze_and_fix method."""\n'
        "\n"
        " mock_issue = Mock(spec=Issue)\n"
        " mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
        ' mock_issue.message = "test coverage issue"\n'
        ' mock_issue.file_path = "/test/path.py"\n'
        "\n"
        f" result = await {class_name.lower()}_instance.analyze_and_fix(mock_issue)\n"
        " assert isinstance(result, FixResult)\n"
        " assert hasattr(result, 'success')\n"
        " assert hasattr(result, 'confidence')"
    )


def _generate_generic_agent_method_test(class_name: str, method_name: str) -> str:
    return (
        " @pytest.mark.asyncio\n"
        f" async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name}.{method_name} method."""\n'
        " try:\n"
        f" method = getattr({class_name.lower()}_instance, "
        f'"{method_name}", None)\n'
        f" assert method is not None, "
        f'f"Method {method_name} should exist"\n'
        "\n"
        " if asyncio.iscoroutinefunction(method):\n"
        " result = await method()\n"
        " else:\n"
        " result = method()\n"
        "\n"
        " assert result is not None or result is None\n"
        " except (TypeError, NotImplementedError):\n"
        f' pytest.skip(f"Method {method_name} requires specific arguments")\n'
        " except Exception as e:\n"
        f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
    )


def _generate_async_method_test(class_name: str, method_name: str) -> str:
    return (
        " @pytest.mark.asyncio\n"
        f" async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name}.{method_name} method."""\n'
        " try:\n"
        f" method = getattr({class_name.lower()}_instance, "
        f'"{method_name}", None)\n'
        f" assert method is not None, "
        f'f"Method {method_name} should exist"\n'
        "\n"
        " if asyncio.iscoroutinefunction(method):\n"
        " result = await method()\n"
        " else:\n"
        " result = method()\n"
        "\n"
        " assert result is not None or result is None\n"
        "\n"
        " except (TypeError, NotImplementedError):\n"
        f' pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
        " except Exception as e:\n"
        f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
    )


def _generate_default_method_test(class_name: str, method_name: str) -> str:
    return (
        f" def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name}.{method_name} method."""\n'
        " try:\n"
        f" method = getattr({class_name.lower()}_instance, "
        f'"{method_name}", None)\n'
        f" assert method is not None, "
        f'f"Method {method_name} should exist"\n'
        "\n"
        " result = method()\n"
        " assert result is not None or result is None\n"
        "\n"
        " except (TypeError, NotImplementedError):\n"
        f' pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
        " except Exception as e:\n"
        f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
    )


async def _generate_class_property_test(
    cls: dict[str, Any],
    module_category: str,
) -> str:
    class_name = cls["name"]

    if module_category not in ("service", "manager", "agent"):
        return ""

    return (
        f" def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
        f' """Test {class_name} properties and attributes."""\n'
        "\n"
        f" assert hasattr({class_name.lower()}_instance, '__dict__') or \\\n"
        f" hasattr({class_name.lower()}_instance, '__slots__')\n"
        "\n"
        f" str_repr = str({class_name.lower()}_instance)\n"
        " assert str_repr\n"
        f' assert "{class_name}" in str_repr or "{class_name.lower()}" in \\\n'
        " str_repr.lower()"
    )


async def _generate_integration_tests(
    module_file: Path,
    functions: list[dict[str, Any]],
    classes: list[dict[str, Any]],
    module_category: str,
) -> str:
    if module_category not in ("service", "manager", "core"):
        return ""

    if len(functions) < 3 and len(classes) < 2:
        return ""

    return (
        "\n\n"
        " @pytest.mark.integration\n"
        f" def test_{module_file.stem}_integration(self):\n"
        f' """Integration test for {module_file.stem} module functionality."""\n'
        "\n"
        ' pytest.skip("Integration test needs manual implementation")\n'
        "\n"
        " @pytest.mark.integration\n"
        " @pytest.mark.asyncio\n"
        f" async def test_{module_file.stem}_async_integration(self):\n"
        f' """Async integration test for {module_file.stem} module."""\n'
        "\n"
        ' pytest.skip("Async integration test needs manual implementation")\n'
        "\n"
        " @pytest.mark.performance\n"
        f" def test_{module_file.stem}_performance(self):\n"
        f' """Basic performance test for {module_file.stem} module."""\n'
        "\n"
        ' pytest.skip("Performance test needs manual implementation")'
    )


def _generate_default_args(args: list[str]) -> str:
    if not args or args == ["self"]:
        return ""

    filtered_args = [arg for arg in args if arg != "self"]
    if not filtered_args:
        return ""

    placeholders = []
    for arg in filtered_args:
        if "path" in arg.lower():
            placeholders.append('Path("test")')
        elif "str" in arg.lower() or "name" in arg.lower():
            placeholders.append('"test"')
        elif "int" in arg.lower() or "count" in arg.lower():
            placeholders.append("1")
        elif "bool" in arg.lower():
            placeholders.append("True")
        else:
            placeholders.append("None")

    return ", ".join(placeholders)


def _categorize_module(relative_path: str) -> str:
    if "managers/" in relative_path:
        return "manager"
    if "services/" in relative_path:
        return "service"
    if "core/" in relative_path:
        return "core"
    if "agents/" in relative_path:
        return "agent"
    if "models/" in relative_path:
        return "model"
    if "executors/" in relative_path:
        return "executor"
    return "utility"


# ---------------------------------------------------------------------------
# Coverage analysis and module/function discovery (from TestCoverageAnalyzer)
# ---------------------------------------------------------------------------


async def analyze_coverage(project_path: Path) -> dict[str, Any]:
    try:
        coverage_data = await _get_existing_coverage_data(project_path)
        if coverage_data:
            return coverage_data

        returncode, _, stderr = await _run_coverage_command_stub()

        if returncode != 0:
            return _handle_coverage_command_failure(stderr)

        return await _process_coverage_results_enhanced(project_path)

    except Exception:
        return _create_default_coverage_result()


async def _get_existing_coverage_data(project_path: Path) -> dict[str, Any] | None:
    try:
        json_report = project_path / "coverage.json"
        if json_report.exists():
            content = _read_file(json_report)
            if content:
                coverage_json = json.loads(content)
                return _parse_coverage_json(coverage_json, project_path)

        coverage_file = project_path / ".coverage"
        if coverage_file.exists():
            return await _process_coverage_results_enhanced(project_path)
    except Exception:
        return None

    return None


def _parse_coverage_json(
    coverage_json: dict[str, Any],
    project_path: Path,
) -> dict[str, Any]:
    try:
        totals = coverage_json.get("totals", {})
        current_coverage = totals.get("percent_covered", 0) / 100.0

        uncovered_modules = []
        files = coverage_json.get("files", {})

        for file_path, file_data in files.items():
            if file_data.get("summary", {}).get("percent_covered", 100) < 80:
                rel_path = str(Path(file_path).relative_to(project_path))
                uncovered_modules.append(rel_path)

        return {
            "below_threshold": current_coverage < 0.8,
            "current_coverage": current_coverage,
            "uncovered_modules": uncovered_modules[:15],
            "missing_lines": totals.get("num_statements", 0)
            - totals.get("covered_lines", 0),
            "total_lines": totals.get("num_statements", 0),
        }

    except Exception:
        return _create_default_coverage_result()


async def _run_coverage_command_stub() -> tuple[int, str, str]:
    return 1, "", "Coverage command not available in helper"


def _handle_coverage_command_failure(stderr: str) -> dict[str, Any]:
    return _create_default_coverage_result()


async def _process_coverage_results_enhanced(project_path: Path) -> dict[str, Any]:
    coverage_file = project_path / ".coverage"
    if not coverage_file.exists():
        return _create_default_coverage_result()

    uncovered_modules = await _find_uncovered_modules_enhanced(project_path)
    untested_functions = await _find_untested_functions_enhanced(project_path)

    current_coverage = await _estimate_current_coverage(project_path)

    return {
        "below_threshold": current_coverage < 0.8,
        "current_coverage": current_coverage,
        "uncovered_modules": uncovered_modules[:15],
        "untested_functions": untested_functions[:20],
        "coverage_gaps": await _identify_coverage_gaps(project_path),
        "improvement_potential": _calculate_improvement_potential(
            len(uncovered_modules),
            len(untested_functions),
        ),
    }


async def _estimate_current_coverage(project_path: Path) -> float:
    try:
        source_files: list[Path] = list((project_path / "crackerjack").rglob("*.py"))
        source_files = [f for f in source_files if not f.name.startswith("test_")]

        test_files: list[Path] = list((project_path / "tests").rglob("test_*.py"))

        if not source_files:
            return 0.0

        coverage_ratio = len(test_files) / len(source_files)

        return min(coverage_ratio * 0.6, 0.9)

    except Exception:
        return 0.1


def _calculate_improvement_potential(
    uncovered_modules: int,
    untested_functions: int,
) -> dict[str, Any]:
    if uncovered_modules == untested_functions == 0:
        return {"percentage_points": 0, "priority": "low"}

    module_improvement = uncovered_modules * 2.5
    function_improvement = untested_functions * 0.8

    total_potential = min(module_improvement + function_improvement, 40)

    priority = (
        "high" if total_potential > 15 else "medium" if total_potential > 5 else "low"
    )

    return {
        "percentage_points": round(total_potential, 1),
        "priority": priority,
        "module_contribution": round(module_improvement, 1),
        "function_contribution": round(function_improvement, 1),
    }


def _create_default_coverage_result() -> dict[str, Any]:
    return {
        "below_threshold": True,
        "current_coverage": 0.0,
        "uncovered_modules": [],
    }


async def _find_uncovered_modules_enhanced(project_path: Path) -> list[dict[str, Any]]:
    package_dir = project_path / "crackerjack"
    if not package_dir.exists():
        return []

    py_files = [
        py_file
        for py_file in package_dir.rglob("*.py")
        if not should_skip_module_for_coverage(py_file)
        and not has_corresponding_test(str(py_file), project_path)
    ]

    results: list[dict[str, Any] | BaseException] = await asyncio.gather(
        *(_analyze_module_priority(py_file, project_path) for py_file in py_files),
        return_exceptions=True,
    )

    uncovered = [
        r for r in results if isinstance(r, dict) and not isinstance(r, Exception)
    ]
    uncovered.sort(key=operator.itemgetter("priority_score"), reverse=True)
    return uncovered[:15]


async def _analyze_module_priority(
    py_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    try:
        content = _read_file(py_file) or ""
        ast.parse(content)

        functions = await extract_functions_from_file(py_file)
        classes = await extract_classes_from_file(py_file)

        priority_score = 0

        rel_path = str(py_file.relative_to(project_path))
        if any(
            core_path in rel_path
            for core_path in ("managers/", "services/", "core/", "agents/")
        ):
            priority_score += 10

        priority_score += len(functions) * 2
        priority_score += len(classes) * 3

        public_functions = [f for f in functions if not f["name"].startswith("_")]
        priority_score += len(public_functions) * 2

        lines_count = len(content.split("\n"))
        if lines_count > 100:
            priority_score += 5
        elif lines_count > 50:
            priority_score += 2

        return {
            "path": rel_path,
            "absolute_path": str(py_file),
            "priority_score": priority_score,
            "function_count": len(functions),
            "class_count": len(classes),
            "public_function_count": len(public_functions),
            "lines_count": lines_count,
            "category": _categorize_module(rel_path),
        }

    except Exception:
        return {
            "path": str(py_file.relative_to(project_path)),
            "absolute_path": str(py_file),
            "priority_score": 1,
            "function_count": 0,
            "class_count": 0,
            "public_function_count": 0,
            "lines_count": 0,
            "category": "unknown",
        }


async def _find_untested_functions_enhanced(
    project_path: Path,
) -> list[dict[str, Any]]:
    package_dir = project_path / "crackerjack"
    if not package_dir.exists():
        return []

    py_files = [
        py_file
        for py_file in package_dir.rglob("*.py")
        if not should_skip_file_for_testing(py_file)
    ]

    file_results: list[list[dict[str, Any]] | BaseException] = await asyncio.gather(
        *(
            _find_untested_functions_in_file_enhanced(py_file, project_path)
            for py_file in py_files
        ),
        return_exceptions=True,
    )

    untested: list[dict[str, Any]] = []
    for result in file_results:
        if isinstance(result, list) and not isinstance(result, Exception):
            untested.extend(result)

    untested.sort(key=operator.itemgetter("testing_priority"), reverse=True)
    return untested[:20]


async def _find_untested_functions_in_file_enhanced(
    py_file: Path,
    project_path: Path,
) -> list[dict[str, Any]]:
    untested: list[dict[str, Any]] = []

    with suppress(Exception):
        functions = await extract_functions_from_file(py_file)
        for func in functions:
            if not await function_has_test(func, py_file, project_path):
                func_info = await _analyze_function_testability(
                    func,
                    py_file,
                    project_path,
                )
                untested.append(func_info)

    return untested


async def _analyze_function_testability(
    func: dict[str, Any],
    py_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    try:
        func_info = {
            "name": func["name"],
            "file": str(py_file),
            "relative_file": str(py_file.relative_to(project_path)),
            "line": func.get("line", 1),
            "signature": func.get("signature", ""),
            "args": func.get("args", []),
            "returns": func.get("returns", "Any"),
            "testing_priority": 0,
            "complexity": "simple",
            "test_strategy": "basic",
        }

        priority = 0

        if not func["name"].startswith("_"):
            priority += 10

        arg_count = len(func.get("args", []))
        if arg_count > 3:
            priority += 5
            func_info["complexity"] = "complex"
            func_info["test_strategy"] = "parametrized"
        elif arg_count > 1:
            priority += 2
            func_info["complexity"] = "moderate"

        if any(
            core_path in str(func_info["relative_file"])
            for core_path in ("managers/", "services/", "core/")
        ):
            priority += 8

        if func.get("is_async", False):
            priority += 3
            func_info["test_strategy"] = "async"

        func_info["testing_priority"] = priority

        return func_info

    except Exception:
        return {
            "name": func.get("name", "unknown"),
            "file": str(py_file),
            "relative_file": str(py_file.relative_to(project_path)),
            "line": func.get("line", 1),
            "testing_priority": 1,
            "complexity": "unknown",
            "test_strategy": "basic",
        }


async def _identify_coverage_gaps(project_path: Path) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    with suppress(Exception):
        package_dir = project_path / "crackerjack"
        tests_dir = project_path / "tests"

        if not package_dir.exists() or not tests_dir.exists():
            return []

        py_files = [
            py_file
            for py_file in package_dir.rglob("*.py")
            if not should_skip_module_for_coverage(py_file)
        ]

        results: list[dict[str, Any] | BaseException] = await asyncio.gather(
        *(
        _analyze_existing_test_coverage(py_file, project_path)
        for py_file in py_files
        ),
        return_exceptions=True,
        )

        gaps = [
        r
        for r in results
        if isinstance(r, dict) and not isinstance(r, Exception) and r.get("has_gaps")
        ]

    return gaps[:10]


async def _analyze_existing_test_coverage(
    py_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    try:
        test_file_path = await generate_test_file_path(py_file, project_path)

        coverage_info: dict[str, Any] = {
            "source_file": str(py_file.relative_to(project_path)),
            "test_file": test_file_path if test_file_path.exists() else None,
            "has_gaps": True,
            "missing_test_types": [],
            "coverage_score": 0,
        }

        if not test_file_path.exists():
            coverage_info["missing_test_types"] = [
                "basic",
                "edge_cases",
                "error_handling",
            ]
            return coverage_info

        test_content = _read_file(test_file_path) or ""

        missing_types = []
        if "def test_" not in test_content:
            missing_types.append("basic")
        if "@pytest.mark.parametrize" not in test_content:
            missing_types.append("parametrized")
        if "with pytest.raises" not in test_content:
            missing_types.append("error_handling")
        if "mock" not in test_content.lower():
            missing_types.append("mocking")

        coverage_info["missing_test_types"] = missing_types
        # Preserved verbatim from TestCoverageAnalyzer._analyze_existing_test_coverage:
        # this assigns the *list* `missing_types` to `has_gaps`, not a bool. See
        # module docstring for the distinction versus the agent's own
        # `analyze_existing_test_coverage` below, which computes a real bool.
        coverage_info["has_gaps"] = missing_types
        coverage_info["coverage_score"] = max(0, 100 - len(missing_types) * 25)

        return coverage_info

    except Exception:
        return {
            "source_file": str(py_file.relative_to(project_path)),
            "test_file": None,
            "has_gaps": True,
            "missing_test_types": ["basic"],
            "coverage_score": 0,
        }


async def create_tests_for_module(
    module_path: str,
    project_path: Path,
) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    with suppress(Exception):
        test_results = await _generate_module_tests(module_path, project_path)
        fixes.extend(test_results["fixes"])
        files.extend(test_results["files"])

    return {"fixes": fixes, "files": files}


async def _generate_module_tests(
    module_path: str,
    project_path: Path,
) -> dict[str, list[str]]:
    module_file = Path(module_path)
    if not await _is_module_valid(module_file):
        return {"fixes": [], "files": []}

    functions = await extract_functions_from_file(module_file)
    classes = await extract_classes_from_file(module_file)

    if not functions and not classes:
        return {"fixes": [], "files": []}

    return await _create_test_artifacts(module_file, functions, classes, project_path)


async def _is_module_valid(module_file: Path) -> bool:
    return module_file.exists()


async def _create_test_artifacts(
    module_file: Path,
    functions: list[dict[str, Any]],
    classes: list[dict[str, Any]],
    project_path: Path,
) -> dict[str, list[str]]:
    test_file_path = await generate_test_file_path(module_file, project_path)
    test_content = await generate_test_content(
        module_file,
        functions,
        classes,
        project_path,
    )

    if _write_file(test_file_path, test_content):
        return {
            "fixes": [f"Created test file for {module_file}"],
            "files": [str(test_file_path)],
        }

    return {"fixes": [], "files": []}


async def create_tests_for_file(
    file_path: str,
    project_path: Path,
) -> dict[str, list[str]]:
    if has_corresponding_test(file_path, project_path):
        return {"fixes": [], "files": []}

    return await create_tests_for_module(file_path, project_path)


async def find_untested_functions(project_path: Path) -> list[dict[str, Any]]:
    package_dir = project_path / "crackerjack"
    if not package_dir.exists():
        return []

    py_files = [
        py_file
        for py_file in package_dir.rglob("*.py")
        if not should_skip_file_for_testing(py_file)
    ]

    file_results: list[list[dict[str, Any]] | BaseException] = await asyncio.gather(
        *(
            _find_untested_functions_in_file(py_file, project_path)
            for py_file in py_files
        ),
        return_exceptions=True,
    )

    untested: list[dict[str, Any]] = []
    for result in file_results:
        if isinstance(result, list) and not isinstance(result, Exception):
            untested.extend(result)

    return untested[:10]


async def _find_untested_functions_in_file(
    py_file: Path,
    project_path: Path,
) -> list[dict[str, Any]]:
    untested: list[dict[str, Any]] = []

    functions = await extract_functions_from_file(py_file)
    for func in functions:
        if not await function_has_test(func, py_file, project_path):
            untested.append(_create_untested_function_info(func, py_file))

    return untested


def _create_untested_function_info(
    func: dict[str, Any],
    py_file: Path,
) -> dict[str, Any]:
    return {
        "name": func["name"],
        "file": str(py_file),
        "line": func.get("line", 1),
        "signature": func.get("signature", ""),
    }


async def create_test_for_function(
    func_info: dict[str, Any],
    project_path: Path,
) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    with suppress(Exception):
        func_file = Path(func_info["file"])

        test_file_path = await generate_test_file_path(func_file, project_path)

        if test_file_path.exists():
            existing_content = _read_file(test_file_path) or ""
            new_test = await generate_function_test(func_info)

            updated_content = existing_content.rstrip() + "\n\n" + new_test
            if _write_file(test_file_path, updated_content):
                fixes.append(f"Added test for function {func_info['name']}")
                files.append(str(test_file_path))
        else:
            test_content = await generate_function_test(func_info)
            if _write_file(test_file_path, test_content):
                fixes.append(f"Created test file with test for {func_info['name']}")
                files.append(str(test_file_path))

    return {"fixes": fixes, "files": files}


# ---------------------------------------------------------------------------
# Agent-level duplicate/override methods (TestCreationAgent's own logic,
# distinct from -- and not reachable from -- the TestCoverageAnalyzer
# versions above; see module docstring)
# ---------------------------------------------------------------------------


async def analyze_module_priority(
    module_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    module_info = await _analyze_module_priority(module_file, project_path)

    with suppress(Exception):
        content = _read_file(module_file) or ""
        tree = ast.parse(content)
        public_top_level = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.col_offset == 0
        and not node.name.startswith("_")
        ]
        module_info["public_function_count"] = len(public_top_level)

    return module_info


async def identify_coverage_gaps(project_path: Path) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    package_dir = project_path / "crackerjack"
    if not package_dir.exists():
        return gaps

    for py_file in package_dir.rglob("*.py"):
        if should_skip_module_for_coverage(py_file):
            continue

        coverage_info = await analyze_existing_test_coverage(py_file, project_path)
        if coverage_info.get("has_gaps"):
            gaps.append(coverage_info)

    return gaps[:10]


async def analyze_existing_test_coverage(
    module_file: Path,
    project_path: Path,
) -> dict[str, Any]:
    test_file_path = await generate_test_file_path(module_file, project_path)

    coverage_info: dict[str, Any] = {
        "source_file": str(module_file.relative_to(project_path)),
        "test_file": test_file_path if test_file_path.exists() else None,
        "has_gaps": True,
        "missing_test_types": [],
        "coverage_score": 0,
    }

    if not test_file_path.exists():
        coverage_info["missing_test_types"] = [
            "basic",
            "edge_cases",
            "error_handling",
        ]
        return coverage_info

    test_content = _read_file(test_file_path) or ""

    missing_types: list[str] = []
    if "def test_" not in test_content:
        missing_types.append("basic")
    if "@pytest.mark.parametrize" not in test_content:
        missing_types.append("parametrized")
    if "with pytest.raises" not in test_content:
        missing_types.append("error_handling")
    if "mock" not in test_content.lower():
        missing_types.append("mocking")

    coverage_info["missing_test_types"] = missing_types
    coverage_info["has_gaps"] = len(missing_types) > 0
    coverage_info["coverage_score"] = max(0, 100 - len(missing_types) * 25)

    return coverage_info


async def find_untested_functions_in_file(
    test_file: Path,
    project_path: Path,
) -> list[dict[str, Any]]:
    functions = await extract_functions_from_file(test_file)
    return [
        {
            "name": func["name"],
            "file": str(test_file),
            "line": func.get("line", 1),
            "signature": func.get("signature", ""),
        }
        for func in functions
        if not await function_has_test(func, test_file, project_path)
    ]


def get_enhanced_test_creation_recommendations() -> list[str]:
    return [
        "Run 'python -m crackerjack -t' to execute comprehensive coverage analysis",
        (
            "Focus on testing high-priority functions in managers/ services/ "
            "and core/ modules"
        ),
        (
            "Implement parametrized tests (@pytest.mark.parametrize) "
            "for functions with multiple arguments"
        ),
        "Add edge case testing for boundary conditions and error scenarios",
        "Use fixtures for complex object instantiation and dependency injection",
        "Consider integration tests for modules with multiple classes/functions",
        "Add async tests for coroutine functions using @pytest.mark.asyncio",
        "Mock external dependencies to ensure isolated unit testing",
        "Target >= 10% coverage improvement through systematic test creation",
        "Validate generated tests are syntactically correct before committing",
    ]


# ---------------------------------------------------------------------------
# Top-level orchestration (from TestCreationAgent.analyze_and_fix and its
# confidence/recommendation helpers -- collapses the original 10-method
# pure pass-through dispatch chain; see module docstring)
# ---------------------------------------------------------------------------


def _calculate_confidence(
    success: bool,
    fixes_applied: list[str],
    files_modified: list[str],
) -> float:
    if not success:
        return 0.0

    confidence = 0.5

    test_file_fixes = [f for f in fixes_applied if "test file" in f.lower()]
    function_fixes = [f for f in fixes_applied if "function" in f.lower()]
    coverage_fixes = [f for f in fixes_applied if "coverage" in f.lower()]

    if test_file_fixes:
        confidence += 0.25
    if function_fixes:
        confidence += 0.15
    if coverage_fixes:
        confidence += 0.1

    if len(files_modified) > 1:
        confidence += 0.1

    return min(confidence, 0.95)


def _generate_recommendations(success: bool) -> list[str]:
    if success:
        return [
            "Generated comprehensive test suite",
            "Consider running pytest to validate new tests",
            "Review generated tests for edge cases",
        ]
    return [
        "No test creation opportunities identified",
        "Consider manual test creation for complex scenarios",
    ]


def _create_test_creation_result(
    fixes_applied: list[str],
    files_modified: list[str],
) -> FixResult:
    # Preserved verbatim from TestCreationAgent._create_test_creation_result:
    # `success` is assigned the *list* `fixes_applied`, not `bool(fixes_applied)`.
    # See module docstring for the full quirk explanation.
    success = fixes_applied

    confidence = _calculate_confidence(success, fixes_applied, files_modified)  # type: ignore[arg-type]

    return FixResult(
        success=success,  # type: ignore[arg-type]
        confidence=confidence,
        fixes_applied=fixes_applied,
        remaining_issues=[],
        recommendations=_generate_recommendations(success),  # type: ignore[arg-type]
        files_modified=files_modified,
    )


def _create_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Failed to create tests: {error}"],
        recommendations=[
            "Manual test creation may be required",
            "Check existing test structure and patterns",
        ],
    )


async def _apply_coverage_based_fixes(project_path: Path) -> tuple[list[str], list[str]]:
    fixes_applied: list[str] = []
    files_modified: list[str] = []

    coverage_analysis = await analyze_coverage(project_path)

    if coverage_analysis["below_threshold"]:
        for module_path in coverage_analysis["uncovered_modules"]:
            test_fixes = await create_tests_for_module(module_path, project_path)
            fixes_applied.extend(test_fixes["fixes"])
            files_modified.extend(test_fixes["files"])

    return fixes_applied, files_modified


async def _apply_file_specific_fixes(
    file_path: str | None,
    project_path: Path,
) -> tuple[list[str], list[str]]:
    if not file_path:
        return [], []

    file_fixes = await create_tests_for_file(file_path, project_path)
    return file_fixes["fixes"], file_fixes["files"]


async def _apply_function_specific_fixes(
    project_path: Path,
) -> tuple[list[str], list[str]]:
    fixes_applied: list[str] = []
    files_modified: list[str] = []

    untested_functions = await find_untested_functions(project_path)
    for func_info in untested_functions[:5]:
        func_fixes = await create_test_for_function(func_info, project_path)
        fixes_applied.extend(func_fixes["fixes"])
        files_modified.extend(func_fixes["files"])

    return fixes_applied, files_modified


async def _apply_test_creation_fixes(
    issue: Issue,
    project_path: Path,
) -> tuple[list[str], list[str]]:
    fixes_applied: list[str] = []
    files_modified: list[str] = []

    coverage_fixes, coverage_files = await _apply_coverage_based_fixes(project_path)
    fixes_applied.extend(coverage_fixes)
    files_modified.extend(coverage_files)

    file_fixes, file_modified = await _apply_file_specific_fixes(
        issue.file_path,
        project_path,
    )
    fixes_applied.extend(file_fixes)
    files_modified.extend(file_modified)

    function_fixes, function_files = await _apply_function_specific_fixes(project_path)
    fixes_applied.extend(function_fixes)
    files_modified.extend(function_files)

    return fixes_applied, files_modified


async def create_tests_for_issue(issue: Issue, project_path: Path) -> FixResult:
    try:
        fixes_applied, files_modified = await _apply_test_creation_fixes(
            issue,
            project_path,
        )
        return _create_test_creation_result(fixes_applied, files_modified)

    except Exception as e:
        return _create_error_result(e)


__all__ = [
    "analyze_coverage",
    "analyze_existing_test_coverage",
    "analyze_module_priority",
    "create_test_for_function",
    "create_tests_for_file",
    "create_tests_for_issue",
    "create_tests_for_module",
    "extract_classes_from_file",
    "extract_functions_from_file",
    "find_untested_functions",
    "find_untested_functions_in_file",
    "function_has_test",
    "generate_comprehensive_test_content",
    "generate_function_test",
    "generate_test_content",
    "generate_test_file_path",
    "get_enhanced_test_creation_recommendations",
    "get_relative_module_path",
    "has_corresponding_test",
    "identify_coverage_gaps",
    "should_skip_file_for_testing",
    "should_skip_module_for_coverage",
]
