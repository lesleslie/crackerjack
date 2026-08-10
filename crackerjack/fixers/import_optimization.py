"""Deterministic AST/vulture-based import-optimization fixer.

Extracted from ``crackerjack.agents.import_optimization_agent.ImportOptimizationAgent``
(2,134 lines), which does not delegate to any ``agents/helpers/*`` class --
it is fully self-contained aside from ``AgentContext`` (framework file-I/O
wrapper) and ``SubAgent.log`` (a no-op ``pass`` on the base class).
Confirmed via full read of the source file: no LLM/bridge/coordinator/
semantic-search references anywhere in the class.

What was intentionally dropped versus the original ``ImportOptimizationAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__``, ``log``,
  ``can_handle``, ``get_supported_types``, and ``analyze_and_fix`` (a
  one-line ``return await self.fix_issue(issue)`` wrapper) -- these only
  ever decided *whether* and *how confidently* this fixer should run for a
  given ``Issue``, or forwarded to the real entry point; that routing job
  belongs to whatever calls into this module now, not to the module itself.
- ``agent_registry.register(ImportOptimizationAgent)`` -- registry plumbing.
- ``self.log(...)`` calls (in ``_handle_parse_error`` and
  ``_analyze_single_file_metrics``) -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect (same
  treatment as every other ``crackerjack/fixers/*.py`` extraction so far).
  The exception variable that existed only to feed that no-op log call
  (``_handle_parse_error``'s ``e: Exception`` parameter,
  ``_analyze_single_file_metrics``'s ``except Exception as e:`` binding) is
  dropped along with it; both functions' control flow (return an empty
  ``ImportAnalysis`` / return ``None`` on any parse or analysis failure) is
  unchanged.
- ``_initialize_import_containers`` -- dead code with no callers anywhere in
  the original source (verified via grep for
  ``self._initialize_import_containers(``); ``_extract_import_information``
  builds its own ``module_imports``/``all_imports`` containers inline
  instead of calling it. Never wired into the import-extraction pipeline.
- ``AgentContext``-specific file I/O for ``_apply_safe_init_import_fallback``
  and ``_apply_direct_import_fix`` (the two call sites that used
  ``self.context.write_file_content``): its path-traversal check,
  ``wrap_long_lines`` post-processing (which itself imports from the
  to-be-removed ``crackerjack.ai_fix`` package), and syntax/duplicate-
  top-level-definition validation -- replaced with direct ``pathlib.Path``
  reads/writes via ``_read_file``/``_write_file`` below (same helpers,
  byte-for-byte, as ``security.py``/``documentation.py``/``dry.py``/
  ``formatting.py``). Real file I/O is still performed; only the framework
  wrapper around it is gone. This is distinct from
  ``_apply_optimizations_and_prepare_results``'s read/write path
  (``_read_and_optimize_file``/``_write_optimized_content``): the *original*
  already bypassed ``AgentContext`` there and used raw ``Path.open()``
  reads/writes directly, so that path is preserved unchanged below (still
  raw ``Path.open()``, not routed through ``_read_file``/``_write_file``) to
  stay faithful to the original's own read/write split.
- ``cwd=self.context.project_path`` pinning on the ``uv run vulture ...``
  subprocess call in ``_run_vulture_analysis`` -- Task 22a restored this:
  ``_run_vulture_analysis`` now takes a ``project_root: Path`` parameter and
  passes it as ``cwd`` to ``subprocess.run``, threaded from
  ``fix_import_issue``'s existing ``project_root`` parameter down through
  ``_process_import_optimization_issue``/``analyze_file``/
  ``_parse_and_analyze_file``/``_detect_unused_imports``, and separately
  from ``get_diagnostics``'s existing ``project_root`` parameter down
  through ``_analyze_file_sample``/``_analyze_single_file_metrics``. Real
  subprocess execution is still performed, with the same
  ``check=False``/``capture_output=True``/``timeout=30`` semantics as the
  original.
- ``AgentContext.project_path``: threaded through explicitly as a
  ``project_root: Path`` parameter wherever it is real, load-bearing logic
  (project-wide symbol search for undefined-name/``__all__``-export fixes,
  and the diagnostics file sampler) -- ``_find_project_symbol_import``,
  ``_find_project_symbol_imports``, ``_path_to_module_name``,
  ``_get_python_files``/``get_diagnostics``, and transitively through
  ``_fix_undefined_name``, ``_fix_undefined_all_exports``,
  ``_apply_direct_import_fix``, and ``fix_import_issue``. The bulk of the
  analyze/optimize pipeline (``analyze_file`` through
  ``_process_import_optimization_issue``) never touched
  ``self.context.project_path`` at all (confirmed via grep) and needs no
  such parameter.
- Six redundant repeated local ``import re`` statements inside
  ``_create_unused_import_patterns``, ``_remove_from_import_list``,
  ``_is_standard_import_line``, ``_is_from_import_line``,
  ``_extract_import_name_from_standard``, and
  ``_extract_import_names_from_from_import`` -- ``re`` is already imported
  at module scope; consolidated into the single top-level import below.
  Same module object either way, so this is a no-op cleanup, not a
  behavior change (same treatment as ``security.py``'s equivalent
  ``SAFE_PATTERNS`` re-import cleanup).

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix``/``fix_issue`` entry point becomes
``fix_import_issue`` below (same validate/dispatch/apply flow, minus the
``self``/``AgentContext`` plumbing). ``ImportOptimizationAgent`` has no
``FixPlan``/``ChangeSpec`` applicator of its own (confirmed via grep for
``FixPlan``/``execute_fix_plan`` in the original source -- neither appears
anywhere), so unlike ``security.py``/``documentation.py``/``formatting.py``
there is no ``execute_fix_plan`` here to port.

``get_diagnostics`` (plus its exclusive helper chain -- ``_get_python_files``,
``_analyze_file_sample``, ``_analyze_single_file_metrics``,
``_extract_file_metrics``, ``_update_metrics``, ``_build_success_diagnostics``,
``_build_error_diagnostics``) is kept: it is a stateless, real consumer of
``analyze_file`` (samples up to 10 project-wide ``*.py`` files and aggregates
their ``ImportAnalysis`` results), not coordinator dispatch, and it is not
cumulative/session-state the way ``PerformanceAgent.performance_metrics`` was
(each call re-samples fresh from disk) -- so the precedent for dropping that
kind of session bookkeeping does not apply here.

Two pre-existing quirks preserved verbatim, not fixed, per CLAUDE.md Rule 7
("preserve functional requirements... fix the technical issue, not the
requirements"):

1. ``_apply_optimizations_and_prepare_results`` builds
   ``files_modified=[file_path]  # type: ignore`` -- ``file_path`` is a
   ``pathlib.Path``, not a ``str``, so this stores a ``Path`` object in a
   ``FixResult.files_modified: list[str]``-typed field (a pre-existing type
   mismatch, marked ``# type: ignore`` in the original). Contrast this with
   ``_apply_direct_import_fix`` and ``_apply_safe_init_import_fallback``,
   which correctly build ``files_modified=[str(file_path)]``. Preserved
   as-is; see ``TestApplyOptimizationsAndPrepareResults`` in
   ``tests/fixers/test_import_optimization.py`` for a test that pins this
   exact behavior.
2. **The significant one**: ``_extract_import_name_from_line`` does not
   actually extract a bare import name from a real ``vulture`` output line.
   It calls ``SAFE_PATTERNS["extract_unused_import_name"].apply(line)``,
   which does a single ``re.sub`` of the *matched substring* (``unused
   import 'name'``) within ``line``, not a return of the captured group
   alone. The pattern's own ``test_cases`` only ever feed it the bare
   ``"unused import 'module_name'"`` substring (which does happen to reduce
   to the bare name when that's the *entire* input), but a real ``vulture``
   line has a ``<path>:<lineno>: `` prefix and a `` (NN% confidence)``
   suffix around that substring -- confirmed empirically:
   ``uv run vulture --min-confidence 80 <file-with-unused-import>`` emits
   ``"<path>:1: unused import 'os' (90% confidence)\n"``, and applying the
   pattern to that full line yields ``"<path>:1: os (90% confidence)"``, not
   ``"os"``. Every entry ``_detect_unused_imports`` returns for a real
   ``vulture`` run is therefore one of these mangled full-line strings, not
   a clean import name -- which in turn means
   ``_create_unused_import_patterns``/``_remove_unused_imports`` (which
   ``re.escape()`` each "unused import" entry into a pattern like
   ``r"^\\s*import\\s+{escaped}\\s*$"``) can never match a real ``import
   <name>`` line for anything vulture actually found, so the
   vulture-detected-unused-import removal path is a functional no-op in
   practice for any real subprocess invocation. It only "removes" imports
   correctly when ``ImportAnalysis.unused_imports`` is constructed directly
   with clean names (as every ``_optimize_imports``/``_remove_unused_imports``
   test below does), never when populated end-to-end from a real ``vulture``
   run. Preserved as-is; see
   ``TestUnusedImportDetection.test_extract_unused_imports_from_result`` and
   ``TestUnusedImportDetection.test_run_vulture_analysis_real_subprocess``
   for tests that pin this exact behavior against real subprocess output.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import typing as t
from collections import defaultdict
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue
from crackerjack.services.regex_patterns import SAFE_PATTERNS


class ImportAnalysis(t.NamedTuple):
    file_path: Path
    mixed_imports: list[str]
    redundant_imports: list[str]
    unused_imports: list[str]
    optimization_opportunities: list[str]
    import_violations: list[str]


_COMMON_IMPORTS: dict[str, str] = {
    "Any": "from typing import Any",
    "Callable": "from typing import Callable",
    "ClassVar": "from typing import ClassVar",
    "Dict": "from typing import Dict",
    "Iterable": "from typing import Iterable",
    "Iterator": "from typing import Iterator",
    "List": "from typing import List",
    "Mapping": "from typing import Mapping",
    "Optional": "from typing import Optional",
    "Path": "from pathlib import Path",
    "Protocol": "from typing import Protocol",
    "Sequence": "from typing import Sequence",
    "Set": "from typing import Set",
    "TypedDict": "from typing import TypedDict",
    "Union": "from typing import Union",
    "asyncio": "import asyncio",
    "datetime": "import datetime",
    "json": "import json",
    "operator": "import operator",
    "os": "import os",
    "re": "import re",
    "sys": "import sys",
    "tree_sitter": "import tree_sitter",
    "typing": "import typing",
}


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# analyze_file / ast parsing pipeline
# ---------------------------------------------------------------------------


async def analyze_file(file_path: Path, project_root: Path) -> ImportAnalysis:
    if not _is_valid_python_file(file_path):
        return _create_empty_import_analysis(file_path)

    return await _parse_and_analyze_file(file_path, project_root)


def _is_valid_python_file(file_path: Path) -> bool:
    return file_path.exists() and file_path.suffix == ".py"


def _create_empty_import_analysis(file_path: Path) -> ImportAnalysis:
    return ImportAnalysis(file_path, [], [], [], [], [])


async def _parse_and_analyze_file(
    file_path: Path, project_root: Path
) -> ImportAnalysis:
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)
    except (SyntaxError, OSError):
        return _handle_parse_error(file_path)

    unused_imports = await _detect_unused_imports(file_path, project_root)

    return _analyze_imports(file_path, tree, content, unused_imports)


def _handle_parse_error(file_path: Path) -> ImportAnalysis:
    return ImportAnalysis(file_path, [], [], [], [], [])


# ---------------------------------------------------------------------------
# vulture-based unused-import detection
# ---------------------------------------------------------------------------


async def _detect_unused_imports(file_path: Path, project_root: Path) -> list[str]:
    try:
        result = _run_vulture_analysis(file_path, project_root)
        return _extract_unused_imports_from_result(result)
    except (
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        FileNotFoundError,
    ):
        return []


def _run_vulture_analysis(
    file_path: Path, project_root: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "vulture", "--min-confidence", "80", file_path],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _extract_unused_imports_from_result(
    result: subprocess.CompletedProcess[str],
) -> list[str]:
    unused_imports: list[str] = []
    if not _is_valid_vulture_result(result):
        return unused_imports

    for line in result.stdout.strip().split("\n"):
        import_name = _extract_import_name_from_line(line)
        if import_name:
            unused_imports.append(import_name)

    return unused_imports


def _is_valid_vulture_result(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and bool(result.stdout)


def _extract_import_name_from_line(line: str) -> str | None:
    if not line or "unused import" not in line.lower():
        return None

    pattern_obj = SAFE_PATTERNS["extract_unused_import_name"]
    if pattern_obj.test(line):
        return pattern_obj.apply(line)
    return None


# ---------------------------------------------------------------------------
# import extraction / analysis (mixed, redundant, optimization, violations)
# ---------------------------------------------------------------------------


def _analyze_imports(
    file_path: Path,
    tree: ast.AST,
    content: str,
    unused_imports: list[str],
) -> ImportAnalysis:
    analysis_results = _perform_full_import_analysis(tree, content)

    return _create_import_analysis(file_path, analysis_results, unused_imports)


def _create_import_analysis(
    file_path: Path,
    analysis_results: dict[str, list[str]],
    unused_imports: list[str],
) -> ImportAnalysis:
    return ImportAnalysis(
        file_path=file_path,
        mixed_imports=analysis_results["mixed_imports"],
        redundant_imports=analysis_results["redundant_imports"],
        unused_imports=unused_imports,
        optimization_opportunities=analysis_results["optimization_opportunities"],
        import_violations=analysis_results["import_violations"],
    )


def _perform_full_import_analysis(
    tree: ast.AST,
    content: str,
) -> dict[str, list[str]]:
    module_imports, all_imports = _extract_import_information(tree)

    return _perform_import_analysis(module_imports, all_imports, content)


def _perform_import_analysis(
    module_imports: dict[str, list[dict[str, t.Any]]],
    all_imports: list[dict[str, t.Any]],
    content: str,
) -> dict[str, list[str]]:
    return _analyze_import_patterns(
        module_imports,
        all_imports,
        content,
    )


def _analyze_import_patterns(
    module_imports: dict[str, list[dict[str, t.Any]]],
    all_imports: list[dict[str, t.Any]],
    content: str,
) -> dict[str, list[str]]:
    return _analyze_import_aspects(module_imports, all_imports, content)


def _analyze_import_aspects(
    module_imports: dict[str, list[dict[str, t.Any]]],
    all_imports: list[dict[str, t.Any]],
    content: str,
) -> dict[str, list[str]]:
    return _analyze_each_import_aspect(module_imports, all_imports, content)


def _analyze_each_import_aspect(
    module_imports: dict[str, list[dict[str, t.Any]]],
    all_imports: list[dict[str, t.Any]],
    content: str,
) -> dict[str, list[str]]:
    mixed_imports = _find_mixed_imports(module_imports)
    redundant_imports = _find_redundant_imports(all_imports)
    optimization_opportunities = _find_optimization_opportunities(
        module_imports,
    )
    import_violations = _find_import_violations(content, all_imports)

    return {
        "mixed_imports": mixed_imports,
        "redundant_imports": redundant_imports,
        "optimization_opportunities": optimization_opportunities,
        "import_violations": import_violations,
    }


def _extract_import_information(
    tree: ast.AST,
) -> tuple[dict[str, list[dict[str, t.Any]]], list[dict[str, t.Any]]]:
    module_imports: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
    all_imports: list[dict[str, t.Any]] = []

    _process_tree_imports(tree, all_imports, module_imports)

    return module_imports, all_imports


def _process_tree_imports(
    tree: ast.AST,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    _process_all_nodes(tree, all_imports, module_imports)


def _process_all_nodes(
    tree: ast.AST,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    _process_import_statements_in_tree(tree, all_imports, module_imports)


def _process_import_statements_in_tree(
    tree: ast.AST,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    for node in ast.walk(tree):
        _process_node_if_import(node, all_imports, module_imports)


def _process_node_if_import(
    node: ast.AST,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    if isinstance(node, ast.Import):
        _process_standard_import(node, all_imports, module_imports)
    elif isinstance(node, ast.ImportFrom) and node.module:
        _process_from_import(node, all_imports, module_imports)


def _process_standard_import(
    node: ast.Import,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    _process_standard_import_aliases(node, all_imports, module_imports)


def _process_standard_import_aliases(
    node: ast.Import,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    for alias in node.names:
        import_info = {
            "type": "standard",
            "module": alias.name,
            "name": alias.asname or alias.name,
            "line": node.lineno,
        }
        all_imports.append(import_info)
        base_module = alias.name.split(".")[0]
        module_imports.setdefault(base_module, []).append(import_info)


def _process_from_import(
    node: ast.ImportFrom,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    _process_from_import_aliases(node, all_imports, module_imports)


def _process_from_import_aliases(
    node: ast.ImportFrom,
    all_imports: list[dict[str, t.Any]],
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> None:
    if node.module is None:
        return

    for alias in node.names:
        import_info = {
            "type": "from",
            "module": node.module,
            "name": alias.name,
            "asname": alias.asname,
            "line": node.lineno,
        }
        all_imports.append(import_info)
        base_module = node.module.split(".")[0]
        module_imports.setdefault(base_module, []).append(import_info)


def _find_mixed_imports(
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> list[str]:
    mixed: list[str] = []

    mixed.extend(_check_mixed_imports_per_module(module_imports))
    return mixed


def _check_mixed_imports_per_module(
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> list[str]:
    mixed: list[str] = []
    for module, imports in module_imports.items():
        types = {imp["type"] for imp in imports}
        if len(types) > 1:
            mixed.append(module)
    return mixed


def _find_redundant_imports(all_imports: list[dict[str, t.Any]]) -> list[str]:
    seen_modules: set[str] = set()
    redundant: list[str] = []

    redundant.extend(_check_redundant_imports(all_imports, seen_modules))

    return redundant


def _check_redundant_imports(
    all_imports: list[dict[str, t.Any]],
    seen_modules: set[str],
) -> list[str]:
    redundant: list[str] = []

    for imp in all_imports:
        module_key = f"{imp['module']}: {imp['name']}"
        if module_key in seen_modules:
            redundant.append(f"Line {imp['line']}: {imp['module']}.{imp['name']}")
        seen_modules.add(module_key)

    return redundant


def _find_optimization_opportunities(
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> list[str]:
    return _find_consolidation_opportunities(module_imports)


def _find_consolidation_opportunities(
    module_imports: dict[str, list[dict[str, t.Any]]],
) -> list[str]:
    opportunities: list[str] = []

    for module, imports in module_imports.items():
        standard_imports = [imp for imp in imports if imp["type"] == "standard"]
        from_imports = [imp for imp in imports if imp["type"] == "from"]

        if len(standard_imports) >= 2:
            opportunities.append(
                f"Consolidate {len(standard_imports)} standard imports "
                f"from '{module}' into from-import style",
            )

        if len(from_imports) >= 3:
            opportunities.append(
                f"Consider combining {len(from_imports)} from-imports "
                f"from '{module}' into fewer lines",
            )

    return opportunities


def _find_import_violations(
    content: str,
    all_imports: list[dict[str, t.Any]],
) -> list[str]:
    violations = _check_import_ordering(all_imports)

    violations.extend(_check_star_imports(content))

    return violations


def _check_import_ordering(all_imports: list[dict[str, t.Any]]) -> list[str]:
    violations: list[str] = []

    _categorize_imports(all_imports)

    violations.extend(_find_pep8_order_violations(all_imports))

    return violations


def _find_pep8_order_violations(
    all_imports: list[dict[str, t.Any]],
) -> list[str]:
    violations: list[str] = []
    prev_category = 0

    for imp in all_imports:
        module = imp.get("module", "")
        category = _get_import_category(module)

        if category < prev_category:
            violations.append(
                f"Import '{module}' should come before previous imports (PEP 8 ordering)",
            )
        prev_category = max(prev_category, category)

    return violations


def _check_star_imports(content: str) -> list[str]:
    violations: list[str] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        if SAFE_PATTERNS["match_star_import"].test(line.strip()):
            violations.append(f"Line {line_num}: Avoid star imports")

    return violations


def _categorize_imports(
    all_imports: list[dict[str, t.Any]],
) -> dict[int, list[dict[str, t.Any]]]:
    categories: dict[int, list[dict[str, t.Any]]] = defaultdict(list)

    for imp in all_imports:
        module = imp.get("module", "")
        category = _get_import_category(module)
        categories[category].append(imp)

    return categories


def _get_import_category(module: str) -> int:
    if not module:
        return 3
    if module == "__future__":
        return 0

    return _determine_module_category(module)


def _determine_module_category(module: str) -> int:
    base_module = module.split(".")[0]

    if _is_stdlib_module(base_module):
        return 1

    if _is_local_import(module, base_module):
        return 3

    return 2


def _is_stdlib_module(base_module: str) -> bool:
    stdlib_modules = _get_stdlib_modules()
    return base_module in stdlib_modules


def _get_stdlib_modules() -> set[str]:
    return {
        "os",
        "sys",
        "json",
        "ast",
        "re",
        "pathlib",
        "subprocess",
        "typing",
        "collections",
        "functools",
        "itertools",
        "tempfile",
        "contextlib",
        "dataclasses",
        "enum",
        "abc",
        "asyncio",
        "concurrent",
        "urllib",
        "http",
        "socket",
        "ssl",
        "time",
        "datetime",
        "calendar",
        "math",
        "random",
        "hashlib",
        "hmac",
        "base64",
        "uuid",
        "logging",
        "warnings",
    }


def _is_local_import(module: str, base_module: str) -> bool:
    return module.startswith(".") or base_module == "crackerjack"


# ---------------------------------------------------------------------------
# fix_import_issue dispatch (was SubAgent.analyze_and_fix / fix_issue)
# ---------------------------------------------------------------------------


async def fix_import_issue(issue: Issue, project_root: Path) -> FixResult:
    validation_result = _validate_issue(issue)
    if validation_result:
        return validation_result

    file_path = Path(issue.file_path) if issue.file_path else None
    if file_path and file_path.name == "__init__.py":
        direct_fix = await _apply_direct_import_fix(issue, project_root)
        if direct_fix is not None:
            return direct_fix

        safe_fix = _apply_safe_init_import_fallback(issue, file_path)
        if safe_fix is not None:
            return safe_fix

        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                (
                    "Skipped risky import-block optimization for __init__.py; "
                    "requires targeted manual/import-specific fix"
                )
            ],
            recommendations=[
                "Apply targeted noqa/import cleanup for __init__.py exports"
            ],
        )

    direct_fix = await _apply_direct_import_fix(issue, project_root)
    if direct_fix is not None:
        return direct_fix

    return await _process_import_optimization_issue(issue, project_root)


def _apply_safe_init_import_fallback(issue: Issue, file_path: Path) -> FixResult | None:
    content = _read_file(file_path)
    if content is None:
        return None

    code = _extract_issue_rule_code(issue)
    supported_codes = {"F401", "F403", "F405", "F822"}
    if code and code not in supported_codes:
        return None

    lines = content.splitlines()
    fallback_code = code or "F401"
    changed, applied_codes = _apply_init_import_noqa(lines, fallback_code, code)

    if not changed:
        return None

    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"
    if not _write_file(file_path, new_content):
        return None
    return FixResult(
        success=True,
        confidence=0.75,
        fixes_applied=[
            (
                "Applied safe __init__.py import suppression for "
                f"{', '.join(sorted(applied_codes))}"
            )
        ],
        files_modified=[str(file_path)],
    )


def _apply_init_import_noqa(
    lines: list[str],
    fallback_code: str,
    issue_code: str | None,
) -> tuple[bool, set[str]]:
    changed = False
    applied_codes: set[str] = set()

    for index, line in enumerate(lines):
        if not _is_top_level_import_line(line):
            continue
        if _line_already_has_noqa(line, fallback_code):
            continue
        lines[index] = _append_noqa_code(line, fallback_code)
        changed = True
        applied_codes.add(fallback_code)

    if issue_code == "F822":
        changed, applied_codes = _apply_all_declaration_noqa(
            lines, changed, applied_codes
        )

    return changed, applied_codes


def _line_already_has_noqa(line: str, code: str) -> bool:
    return f"# noqa: {code}" in line


def _append_noqa_code(line: str, code: str) -> str:
    if "# noqa:" in line:
        return f"{line.rstrip()}, {code}"
    return f"{line.rstrip()} # noqa: {code}"


def _apply_all_declaration_noqa(
    lines: list[str],
    changed: bool,
    applied_codes: set[str],
) -> tuple[bool, set[str]]:
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("__all__"):
            continue
        if "# noqa: F822" in line:
            return changed, applied_codes
        lines[index] = _append_noqa_code(line, "F822")
        applied_codes.add("F822")
        return True, applied_codes
    return changed, applied_codes


async def _apply_direct_import_fix(
    issue: Issue, project_root: Path
) -> FixResult | None:
    if not issue.file_path:
        return None

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return None

    content = _read_file(file_path)
    if content is None:
        return None

    message_lower = issue.message.lower()
    if _needs_future_import_reorder(issue, content):
        new_content, fixes = _move_future_import(content)
    elif _is_unused_import_issue(issue):
        new_content, fixes = _fix_unused_import_line(issue, content)
    elif _is_star_import_expansion_candidate(issue, content):
        new_content, fixes = _expand_star_import_from_all(issue, content)
    elif _is_import_order_issue(issue):
        new_content, fixes = _sort_from_import_names(content)
    elif _is_import_lint_suppressible(issue):
        new_content, fixes = _suppress_import_lint_issue(issue, content)
    elif "__all__" in message_lower:
        new_content, fixes = _fix_undefined_all_exports(content, project_root)
    else:
        undefined_name = _extract_undefined_name(issue)
        if not undefined_name:
            return None

        new_content, fixes = _fix_undefined_name(content, undefined_name, project_root)

    if new_content == content or not fixes:
        return None

    if not _write_file(file_path, new_content):
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write file: {file_path}"],
        )

    return FixResult(
        success=True,
        confidence=0.85,
        fixes_applied=fixes,
        files_modified=[str(file_path)],
    )


def _is_unused_import_issue(issue: Issue) -> bool:
    message_lower = issue.message.lower()
    return "imported but unused" in message_lower or "unused import" in message_lower


def _is_import_lint_suppressible(issue: Issue) -> bool:
    code = _extract_issue_rule_code(issue)
    return code in {"F401", "F403", "F405"}


def _is_import_order_issue(issue: Issue) -> bool:
    return _extract_issue_rule_code(issue) == "I001"


def _is_star_import_expansion_candidate(issue: Issue, content: str) -> bool:
    code = _extract_issue_rule_code(issue)
    message_lower = issue.message.lower()
    if code not in {"F403", "F405"} and "star import" not in message_lower:
        return False
    return bool(_find_star_import_lines(content.splitlines()))


def _is_star_import_line(line: str) -> bool:
    return bool(re.match(r"^\s*from\s+[\w\.]+\s+import\s+\*\s*(#.*)?$", line))


def _expand_star_import_from_all(issue: Issue, content: str) -> tuple[str, list[str]]:
    lines = content.splitlines()
    star_imports = _find_star_import_lines(lines)
    if not star_imports:
        return content, []

    export_names = _extract_all_export_names(content)
    if not export_names:
        return content, []

    changed_modules: list[str] = []
    changed = False
    for index, module_name, old_line, indent in star_imports:
        new_line = f"{indent}from {module_name} import {', '.join(export_names)}"
        if new_line == old_line:
            continue
        lines[index] = new_line
        changed = True
        if module_name not in changed_modules:
            changed_modules.append(module_name)

    if not changed:
        return content, []

    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"

    return new_content, [
        f"Expanded star import from {', '.join(changed_modules)} using __all__"
    ]


def _find_star_import_lines(
    lines: list[str],
) -> list[tuple[int, str, str, str]]:
    star_imports: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines):
        if not _is_star_import_line(line):
            continue

        module_match = re.match(r"^\s*from\s+([\w\.]+)\s+import\s+\*", line)
        if not module_match:
            continue

        indent = line[: len(line) - len(line.lstrip())]
        star_imports.append((index, module_match.group(1), line, indent))

    return star_imports


def _extract_all_export_names(content: str) -> list[str]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            continue

        names: list[str] = []
        values: ast.AST = node.value
        if isinstance(values, (ast.List, ast.Tuple)):
            for element in values.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    names.append(element.value)
        return names

    return []


def _suppress_import_lint_issue(issue: Issue, content: str) -> tuple[str, list[str]]:
    code = _extract_issue_rule_code(issue)
    if not code or not issue.line_number:
        return content, []

    lines = content.splitlines()
    index = issue.line_number - 1
    if not (0 <= index < len(lines)):
        return content, []

    old_line = lines[index]
    if not old_line.lstrip().startswith(("import ", "from ")):
        import_stmt_index = _find_enclosing_import_statement(lines, index)
        if import_stmt_index is None:
            return content, []
        old_line = lines[import_stmt_index]
        index = import_stmt_index

    if f"# noqa: {code}" in old_line:
        return content, []
    if "# noqa:" in old_line:
        lines[index] = f"{old_line.rstrip()}, {code}"
    else:
        lines[index] = f"{old_line.rstrip()} # noqa: {code}"

    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content, [f"Suppressed import lint rule {code} on import statement"]


def _sort_from_import_names(content: str) -> tuple[str, list[str]]:
    lines = content.splitlines()
    changed = False
    fixes: list[str] = []

    for index, line in enumerate(lines):
        if not line.lstrip().startswith("from ") or "*" in line:
            continue

        new_line = _sort_single_from_import_line(line)
        if new_line is None or new_line == line:
            continue

        lines[index] = new_line
        changed = True
        fixes.append(f"Sorted imported names in line {index + 1}")

    if not changed:
        return content, []

    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content, fixes


def _sort_single_from_import_line(line: str) -> str | None:
    match = re.match(
        r"^(?P<indent>\s*)from\s+(?P<module>[\w\.]+)\s+import\s+(?P<body>.+?)\s*(?P<comment>#.*)?$",
        line,
    )
    if not match:
        return None

    body = match.group("body").strip()
    if not body or body == "*":
        return None

    if body.startswith("(") and body.endswith(")"):
        body = body[1:-1].strip()

    names = [part.strip() for part in body.split(", ") if part.strip()]
    if len(names) < 2:
        return None

    sorted_names = sorted(
        names,
        key=lambda name: (
            0 if name.split(" as ", 1)[0].isupper() else 1,
            name.lower(),
        ),
    )

    new_body = ", ".join(sorted_names)
    comment = match.group("comment") or ""
    return (
        f"{match.group('indent')}from {match.group('module')} import {new_body}"
        f"{(' ' + comment) if comment else ''}"
    )


def _extract_ruff_rule_code(message: str) -> str | None:
    match = re.match(r"^\s*([A-Z]+\d+)\b", message)
    return match.group(1) if match else None


def _extract_issue_rule_code(issue: Issue) -> str | None:
    code = _extract_ruff_rule_code(issue.message)
    if code:
        return code

    for detail in issue.details:
        match = re.search(r"\bcode:\s*([A-Z]+\d+)\b", detail, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def _fix_unused_import_line(issue: Issue, content: str) -> tuple[str, list[str]]:
    if not issue.line_number:
        return content, []

    lines = content.splitlines()
    index = issue.line_number - 1
    if not (0 <= index < len(lines)):
        return content, []

    old_line = lines[index]
    if not old_line.lstrip().startswith(("import ", "from ")):
        import_stmt_index = _find_enclosing_import_statement(lines, index)
        if import_stmt_index is None:
            return content, []
        old_line = lines[import_stmt_index]
        index = import_stmt_index
    if "# noqa: F401" in old_line:
        return content, []

    lines[index] = f"{old_line.rstrip()} # noqa: F401"
    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content, ["Annotated intentionally unused import with noqa: F401"]


def _find_enclosing_import_statement(lines: list[str], issue_index: int) -> int | None:
    for i in range(issue_index, -1, -1):
        stripped = lines[i].lstrip()
        if stripped.startswith(("import ", "from ")) and lines[i] == lines[i].lstrip():
            return i
        if stripped.endswith("):") or stripped.startswith(("def ", "class ")):
            break
    return None


def _needs_future_import_reorder(issue: Issue, content: str) -> bool:
    if "from __future__ import" not in content:
        return False
    if "F404" in issue.message or "__future__" in issue.message.lower():
        lines = content.splitlines()
        for index, line in enumerate(lines):
            if line.strip().startswith("from __future__ import "):
                return index > 0 and any(
                    part.strip()
                    for part in lines[:index]
                    if part.strip() and not part.strip().startswith("#")
                )
    return False


def _move_future_import(content: str) -> tuple[str, list[str]]:
    lines = content.splitlines()
    future_lines = [
        line for line in lines if line.strip().startswith("from __future__ import ")
    ]
    if not future_lines:
        return content, []

    remaining_lines = [
        line for line in lines if not line.strip().startswith("from __future__ import ")
    ]

    insert_index = _find_future_import_insertion_index(remaining_lines)
    for future_line in reversed(future_lines):
        remaining_lines.insert(insert_index, future_line)

    if content.endswith("\n"):
        return "\n".join(remaining_lines) + "\n", [
            "Moved __future__ import to the top of the file"
        ]
    return "\n".join(remaining_lines), [
        "Moved __future__ import to the top of the file"
    ]


# ---------------------------------------------------------------------------
# undefined-name / __all__-export fixing (project-wide symbol search)
# ---------------------------------------------------------------------------


def _extract_undefined_name(issue: Issue) -> str | None:
    patterns = (
        r'Name ["\']?([A-Za-z_][\w\.]*)["\']? is not defined',
        r'Undefined name ["\']?([A-Za-z_][\w\.]*)["\']?',
        r'Name ["\']?([A-Za-z_][\w\.]*)["\']?',
    )
    candidates = [issue.message, *issue.details]
    for candidate in candidates:
        for pattern in patterns:
            match = re.search(pattern, candidate)
            if match:
                return match.group(1)
    return None


def _fix_undefined_name(
    content: str, undefined_name: str, project_root: Path
) -> tuple[str, list[str]]:
    if undefined_name == "t":
        return _insert_import(
            content, "import typing as t", "Added typing alias import"
        )

    if undefined_name.endswith("_AVAILABLE"):
        module_name = undefined_name.removesuffix("_AVAILABLE").lower()
        return _insert_available_guard(content, module_name, undefined_name)

    import_line = _COMMON_IMPORTS.get(undefined_name)
    if import_line:
        return _insert_import(
            content, import_line, f"Added missing import for {undefined_name}"
        )

    project_import = _find_project_symbol_import(undefined_name, project_root)
    if project_import:
        return _insert_import(
            content,
            project_import,
            f"Added project import for {undefined_name}",
        )

    if undefined_name and undefined_name[0].isupper():
        typing_import = _infer_typing_import(undefined_name)
        if typing_import:
            return _insert_import(
                content,
                typing_import,
                f"Added typing import for {undefined_name}",
            )

    return content, []


def _fix_undefined_all_exports(
    content: str, project_root: Path
) -> tuple[str, list[str]]:
    undefined_exports = _collect_undefined_all_exports(content)
    if not undefined_exports:
        return content, []

    symbol_imports = _find_project_symbol_imports(undefined_exports, project_root)
    import_lines: list[str] = []
    for symbol in undefined_exports:
        import_line = symbol_imports.get(symbol) or _find_project_symbol_import(
            symbol, project_root
        )
        if import_line and import_line not in import_lines:
            import_lines.append(import_line)

    if not import_lines:
        return content, []

    new_content = _insert_multiple_imports(content, import_lines)
    if new_content == content:
        return content, []
    return new_content, [
        f"Added project imports for __all__ exports: {', '.join(undefined_exports)}"
    ]


def _collect_undefined_all_exports(content: str) -> list[str]:
    all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not all_match:
        return []

    exports = re.findall(r"""['"]([A-Za-z_]\w*)['"]""", all_match.group(1))
    if not exports:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    defined_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
        elif isinstance(node, ast.Import):
            defined_names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            defined_names.update(alias.asname or alias.name for alias in node.names)

    return [name for name in exports if name not in defined_names]


def _infer_typing_import(undefined_name: str) -> str | None:
    typing_names = {
        "Any",
        "Callable",
        "ClassVar",
        "Dict",
        "Final",
        "Iterable",
        "Iterator",
        "List",
        "Mapping",
        "MutableMapping",
        "MutableSequence",
        "Optional",
        "Protocol",
        "Sequence",
        "Set",
        "Tuple",
        "TypedDict",
        "Union",
    }
    if undefined_name in typing_names:
        return f"from typing import {undefined_name}"
    return None


def _find_project_symbol_import(symbol: str, project_root: Path) -> str | None:
    if not project_root.exists():
        return None

    definition_patterns = (
        rf"^\s*class\s+{re.escape(symbol)}\b",
        rf"^\s*def\s+{re.escape(symbol)}\b",
        rf"^\s*{re.escape(symbol)}\s*=",
    )

    candidates: list[Path] = []
    for path in project_root.rglob("*.py"):
        if _should_skip_symbol_scan_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(
            re.search(pattern, text, re.MULTILINE) for pattern in definition_patterns
        ):
            candidates.append(path)

    if not candidates:
        stdlib_modules: frozenset[str] = getattr(
            sys, "stdlib_module_names", frozenset()
        )
        if symbol in stdlib_modules:
            return f"import {symbol}"

        module_name = symbol.lower()
        module_candidates = [
            project_root / f"{module_name}.py",
            *project_root.rglob(f"{module_name}/__init__.py"),
        ]
        for path in module_candidates:
            if path.exists():
                return f"import {module_name}"
        return None

    module_name = _path_to_module_name(candidates[0], project_root)
    if not module_name:
        return None
    return f"from {module_name} import {symbol}"


def _find_project_symbol_imports(
    symbols: list[str], project_root: Path
) -> dict[str, str]:
    if not project_root.exists():
        return {}

    unresolved: set[str] = {s for s in symbols if s}
    if not unresolved:
        return {}

    definition_patterns = {
        symbol: (
            rf"^\s*class\s+{re.escape(symbol)}\b",
            rf"^\s*def\s+{re.escape(symbol)}\b",
            rf"^\s*{re.escape(symbol)}\s*=",
        )
        for symbol in unresolved
    }

    imports: dict[str, str] = {}
    for path in project_root.rglob("*.py"):
        if _should_skip_symbol_scan_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        module_name = _path_to_module_name(path, project_root)
        if not module_name:
            continue

        matched: list[str] = []
        for symbol in unresolved:
            patterns = definition_patterns[symbol]
            if any(re.search(pattern, text, re.MULTILINE) for pattern in patterns):
                imports[symbol] = f"from {module_name} import {symbol}"
                matched.append(symbol)

        unresolved.difference_update(matched)
        if not unresolved:
            break

    return imports


def _should_skip_symbol_scan_path(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _path_to_module_name(path: Path, project_root: Path) -> str | None:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return None

    if relative.name == "__init__.py":
        relative = relative.parent
    else:
        relative = relative.with_suffix("")

    parts = [part for part in relative.parts if part]
    if not parts:
        return None
    return ".".join(parts)


# ---------------------------------------------------------------------------
# import insertion / __future__-import positioning helpers
# ---------------------------------------------------------------------------


def _insert_import(
    content: str, import_line: str, fix_message: str
) -> tuple[str, list[str]]:
    if import_line in content:
        return content, []

    lines = content.splitlines()
    insert_index = _find_import_insertion_index(lines)
    lines.insert(insert_index, import_line)
    new_content = "\n".join(lines)
    new_content = _normalize_future_import_position(new_content)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content, [fix_message]


def _insert_multiple_imports(content: str, import_lines: list[str]) -> str:
    new_content = content
    for import_line in import_lines:
        if import_line in new_content:
            continue
        lines = new_content.splitlines()
        insert_index = _find_import_insertion_index(lines)
        lines.insert(insert_index, import_line)
        new_content = "\n".join(lines)

    new_content = _normalize_future_import_position(new_content)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content


def _insert_available_guard(
    content: str, module_name: str, constant_name: str
) -> tuple[str, list[str]]:
    guard_block = [
        "try:",
        f" import {module_name}",
        f" {constant_name} = True",
        "except ImportError:",
        f" {constant_name} = False",
    ]

    if "\n".join(guard_block) in content:
        return content, []

    lines = content.splitlines()
    insert_index = _find_import_insertion_index(lines)
    for offset, line in enumerate(guard_block):
        lines.insert(insert_index + offset, line)

    new_content = "\n".join(lines)
    new_content = _normalize_future_import_position(new_content)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content, [
        f"Added availability guard for {module_name}",
    ]


def _find_import_insertion_index(lines: list[str]) -> int:
    start_index = 0
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        tree = None

    if tree and tree.body:
        first_node = tree.body[0]
        docstring = ast.get_docstring(tree, clean=False)
        if docstring and isinstance(first_node, ast.Expr):
            end_lineno = getattr(first_node, "end_lineno", first_node.lineno)
            start_index = end_lineno

    insert_index = start_index
    saw_import = False
    for index in range(start_index, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith(("import ", "from ")):
            saw_import = True
            insert_index = index + 1
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if saw_import:
            return insert_index
        return index

    return insert_index


def _normalize_future_import_position(content: str) -> str:
    lines = content.splitlines()
    future_lines = [
        line for line in lines if line.strip().startswith("from __future__ import ")
    ]
    if not future_lines:
        return content

    remaining_lines = [
        line for line in lines if not line.strip().startswith("from __future__ import ")
    ]
    insert_index = _find_future_import_insertion_index(remaining_lines)
    for future_line in reversed(future_lines):
        remaining_lines.insert(insert_index, future_line)
    return "\n".join(remaining_lines)


def _find_future_import_insertion_index(lines: list[str]) -> int:
    insert_index = 0
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        tree = None

    if tree and tree.body:
        first_node = tree.body[0]
        docstring = ast.get_docstring(tree, clean=False)
        if docstring and isinstance(first_node, ast.Expr):
            insert_index = getattr(first_node, "end_lineno", first_node.lineno)

    while insert_index < len(lines):
        stripped = lines[insert_index].strip()
        if not stripped or stripped.startswith("#"):
            insert_index += 1
            continue
        break

    return insert_index


# ---------------------------------------------------------------------------
# project-wide import optimization (analyze -> optimize -> write)
# ---------------------------------------------------------------------------


async def _process_import_optimization_issue(
    issue: Issue, project_root: Path
) -> FixResult:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            fixes_applied=[],
            remaining_issues=["No file path provided in issue"],
        )
    file_path = Path(issue.file_path)

    analysis = await analyze_file(file_path, project_root)

    if not _are_optimizations_needed(analysis):
        return _create_no_optimization_needed_result()

    return await _apply_optimizations_and_prepare_results(file_path, analysis)


def _create_no_optimization_needed_result() -> FixResult:
    return FixResult(
        success=True,
        confidence=1.0,
        fixes_applied=["No import optimizations needed"],
        remaining_issues=[],
        recommendations=["Import patterns are already optimal"],
        files_modified=[],
    )


def _validate_issue(issue: Issue) -> FixResult | None:
    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided for import optimization"],
        )
    return None


def _are_optimizations_needed(analysis: ImportAnalysis) -> bool:
    return any(
        [
            analysis.mixed_imports,
            analysis.redundant_imports,
            analysis.unused_imports,
            analysis.optimization_opportunities,
            analysis.import_violations,
        ],
    )


async def _apply_optimizations_and_prepare_results(
    file_path: Path,
    analysis: ImportAnalysis,
) -> FixResult:
    try:
        optimized_content = await _read_and_optimize_file(file_path, analysis)
        await _write_optimized_content(file_path, optimized_content)

        changes, remaining_issues = _prepare_fix_results(analysis)
        recommendations = _prepare_recommendations(
            file_path.name,
            remaining_issues,
        )

        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=changes,
            remaining_issues=remaining_issues,
            recommendations=recommendations,
            files_modified=[file_path],  # type: ignore
        )

    except Exception as e:
        return _handle_optimization_error(e)


async def _read_and_optimize_file(
    file_path: Path,
    analysis: ImportAnalysis,
) -> str:
    with file_path.open(encoding="utf-8") as f:
        original_content = f.read()
    optimized_content = await _optimize_imports(original_content, analysis)
    _validate_optimized_content(file_path, optimized_content)
    return optimized_content


def _validate_optimized_content(file_path: Path, content: str) -> None:
    try:
        ast.parse(content)
    except SyntaxError as e:
        raise SyntaxError(
            f"Optimized import rewrite for {file_path} produced invalid Python: {e}"
        ) from e


async def _write_optimized_content(
    file_path: Path,
    optimized_content: str,
) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        f.write(optimized_content)


def _handle_optimization_error(e: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        fixes_applied=[],
        remaining_issues=[f"Failed to optimize imports: {e}"],
        recommendations=["Manual import review needed"],
        files_modified=[],
    )


def _prepare_fix_results(
    analysis: ImportAnalysis,
) -> tuple[list[str], list[str]]:
    changes: list[str] = []
    remaining_issues: list[str] = []

    changes.extend(_get_mixed_import_changes(analysis.mixed_imports))
    changes.extend(_get_redundant_import_changes(analysis.redundant_imports))
    changes.extend(_get_unused_import_changes(analysis.unused_imports))
    changes.extend(
        _get_optimization_opportunity_changes(
            analysis.optimization_opportunities,
        ),
    )

    remaining_issues.extend(
        _get_remaining_violations(analysis.import_violations),
    )

    return changes, remaining_issues


def _get_mixed_import_changes(mixed_imports: list[str]) -> list[str]:
    changes: list[str] = []
    if mixed_imports:
        changes.append(
            f"Standardized mixed imports for modules: {', '.join(mixed_imports)}",
        )
    return changes


def _get_redundant_import_changes(redundant_imports: list[str]) -> list[str]:
    changes: list[str] = []
    if redundant_imports:
        changes.append(
            f"Removed {len(redundant_imports)} redundant imports",
        )
    return changes


def _get_unused_import_changes(unused_imports: list[str]) -> list[str]:
    changes: list[str] = []
    if unused_imports:
        changes.append(
            f"Removed {len(unused_imports)} unused imports: {', '.join(unused_imports[:3])}"
            + ("..." if len(unused_imports) > 3 else ""),
        )
    return changes


def _get_optimization_opportunity_changes(
    optimization_opportunities: list[str],
) -> list[str]:
    changes: list[str] = []
    if optimization_opportunities:
        changes.append(
            f"Applied {len(optimization_opportunities)} import consolidations",
        )
    return changes


def _get_remaining_violations(import_violations: list[str]) -> list[str]:
    remaining_issues: list[str] = []
    if import_violations:
        remaining_issues.extend(import_violations[:3])
    return remaining_issues


def _prepare_recommendations(
    file_name: str,
    remaining_issues: list[str],
) -> list[str]:
    recommendations = [f"Optimized import statements in {file_name}"]
    if remaining_issues:
        recommendations.append(
            "Consider manual review for remaining PEP 8 violations",
        )
    return recommendations


async def _optimize_imports(content: str, analysis: ImportAnalysis) -> str:
    lines = content.splitlines()

    lines = _apply_import_optimizations(lines, analysis)

    optimized = "\n".join(lines)
    optimized = _normalize_future_import_position(optimized)
    if content.endswith("\n"):
        optimized += "\n"
    return optimized


def _apply_import_optimizations(
    lines: list[str],
    analysis: ImportAnalysis,
) -> list[str]:
    return _apply_all_optimization_steps(lines, analysis)


def _apply_all_optimization_steps(
    lines: list[str],
    analysis: ImportAnalysis,
) -> list[str]:
    lines = _remove_unused_imports(lines, analysis.unused_imports)

    lines = _consolidate_mixed_imports(lines, analysis.mixed_imports)

    lines = _remove_redundant_imports(lines, analysis.redundant_imports)

    return _organize_imports_pep8(lines)


def _remove_unused_imports(
    lines: list[str],
    unused_imports: list[str],
) -> list[str]:
    if not unused_imports:
        return lines

    unused_patterns = _create_unused_import_patterns(unused_imports)
    return _filter_unused_import_lines(lines, unused_patterns, unused_imports)


def _create_unused_import_patterns(
    unused_imports: list[str],
) -> list[t.Pattern[str]]:
    unused_patterns: list[t.Pattern[str]] = []
    for unused in unused_imports:
        escaped_unused = re.escape(unused)

        unused_patterns.extend(
            (
                re.compile(f"^\\s*import\\s+{escaped_unused}\\s*$"),
                re.compile(
                    f"^\\s*from\\s+\\w+\\s+import\\s+.*\\b{escaped_unused}\\b",
                ),
            ),
        )
    return unused_patterns


def _filter_unused_import_lines(
    lines: list[str],
    unused_patterns: list[t.Pattern[str]],
    unused_imports: list[str],
) -> list[str]:
    filtered_lines = []
    for line in lines:
        if line != line.lstrip():
            filtered_lines.append(line)
            continue

        should_remove = False
        for pattern in unused_patterns:
            if pattern.search(line):
                if _is_multi_import_line(line):
                    line = _remove_from_import_list(line, unused_imports)
                else:
                    should_remove = True
                break

        if not should_remove and line.strip():
            filtered_lines.append(line)

    return filtered_lines


def _is_multi_import_line(line: str) -> bool:
    return "import" in line and ", " in line


def _remove_from_import_list(line: str, unused_imports: list[str]) -> str:
    for unused in unused_imports:
        escaped_unused = re.escape(unused)
        line = re.sub(rf", ?\s*{escaped_unused}\s*, ?", ", ", line)

        line = SAFE_PATTERNS["clean_import_commas"].apply(line)
        line = SAFE_PATTERNS["clean_trailing_import_comma"].apply(line)
        line = SAFE_PATTERNS["clean_import_prefix"].apply(line)
    return line


def _consolidate_mixed_imports(
    lines: list[str],
    mixed_modules: list[str],
) -> list[str]:
    if not mixed_modules:
        return lines

    import_data = _collect_mixed_module_imports(lines, mixed_modules)
    lines = _remove_old_mixed_imports(lines, import_data["lines_to_remove"])
    return _insert_consolidated_imports(lines, import_data)


def _collect_mixed_module_imports(
    lines: list[str],
    mixed_modules: list[str],
) -> dict[str, t.Any]:
    import_collector = _create_import_collector()

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        for module in mixed_modules:
            _process_mixed_module_line(
                stripped_line,
                module,
                i,
                import_collector,
            )

    return _finalize_import_collection(import_collector)


def _create_import_collector() -> dict[str, t.Any]:
    return {
        "module_imports": defaultdict(set),
        "lines_to_remove": set(),
        "insert_positions": {},
    }


def _finalize_import_collection(
    collector: dict[str, t.Any],
) -> dict[str, t.Any]:
    return {
        "module_imports": collector["module_imports"],
        "lines_to_remove": collector["lines_to_remove"],
        "insert_positions": collector["insert_positions"],
    }


def _process_mixed_module_line(
    line: str,
    module: str,
    line_index: int,
    import_collector: dict[str, t.Any],
) -> None:
    if _is_standard_import_line(line, module):
        _handle_standard_import(line, module, line_index, import_collector)
    elif _is_from_import_line(line, module):
        _handle_from_import(line, module, line_index, import_collector)


def _is_standard_import_line(line: str, module: str) -> bool:
    return bool(re.match(rf"^\s*import\s+{re.escape(module)}(?: \.\w+)*\s*$", line))


def _is_from_import_line(line: str, module: str) -> bool:
    return bool(re.match(rf"^\s*from\s+{re.escape(module)}\s+import\s+", line))


def _handle_standard_import(
    line: str,
    module: str,
    line_index: int,
    import_collector: dict[str, t.Any],
) -> None:
    import_name = _extract_import_name_from_standard(line, module)
    if import_name:
        import_to_add = _determine_import_name(import_name, module)
        _add_import_to_collector(
            module,
            import_to_add,
            line_index,
            import_collector,
        )


def _extract_import_name_from_standard(line: str, module: str) -> str | None:
    match = re.search(rf"import\s+({re.escape(module)}(?: \.\w+)*)", line)
    return match.group(1) if match else None


def _determine_import_name(import_name: str, module: str) -> str:
    if "." in import_name:
        return import_name.split(".")[-1]
    return module


def _add_import_to_collector(
    module: str,
    import_name: str,
    line_index: int,
    import_collector: dict[str, t.Any],
) -> None:
    import_collector["module_imports"][module].add(import_name)
    import_collector["lines_to_remove"].add(line_index)
    if module not in import_collector["insert_positions"]:
        import_collector["insert_positions"][module] = line_index


def _handle_from_import(
    line: str,
    module: str,
    line_index: int,
    import_collector: dict[str, t.Any],
) -> None:
    import_names = _extract_import_names_from_from_import(line, module)
    import_collector["module_imports"][module].update(import_names)
    import_collector["lines_to_remove"].add(line_index)
    if module not in import_collector["insert_positions"]:
        import_collector["insert_positions"][module] = line_index


def _extract_import_names_from_from_import(
    line: str,
    module: str,
) -> list[str]:
    import_part = re.sub(rf"^\s*from\s+{re.escape(module)}\s+import\s+", "", line)
    return [name.strip() for name in import_part.split(", ")]


def _remove_old_mixed_imports(
    lines: list[str],
    lines_to_remove: set[int],
) -> list[str]:
    for i in sorted(lines_to_remove, reverse=True):
        del lines[i]
    return lines


def _insert_consolidated_imports(
    lines: list[str],
    import_data: dict[str, t.Any],
) -> list[str]:
    module_imports = import_data["module_imports"]
    insert_positions = import_data["insert_positions"]
    lines_to_remove = import_data["lines_to_remove"]

    offset = 0
    for module, imports in module_imports.items():
        if module in insert_positions:
            imports_list = sorted(imports)
            consolidated = f"from {module} import {', '.join(imports_list)}"
            insert_pos = insert_positions[module] - offset
            lines.insert(insert_pos, consolidated)
            offset += (
                len([i for i in lines_to_remove if i <= insert_positions[module]]) - 1
            )
    return lines


def _remove_redundant_imports(
    lines: list[str],
    redundant_imports: list[str],
) -> list[str]:
    if not redundant_imports:
        return lines

    seen_imports: set[str] = set()
    filtered_lines = []

    for line in lines:
        normalized = SAFE_PATTERNS["normalize_whitespace"].apply(line.strip())

        if normalized.startswith(("import ", "from ")):
            if normalized not in seen_imports:
                seen_imports.add(normalized)
                filtered_lines.append(line)

        else:
            filtered_lines.append(line)

    return filtered_lines


def _organize_imports_pep8(lines: list[str]) -> list[str]:
    parsed_data = _parse_import_lines(lines)
    import_data, other_lines, import_bounds = parsed_data

    if not import_data:
        return lines

    sorted_imports = _sort_imports_by_pep8_standards(import_data)
    return _rebuild_with_organized_imports(
        sorted_imports,
        other_lines,
        import_bounds,
    )


def _sort_imports_by_pep8_standards(
    import_data: list[tuple[int, str, str]],
) -> list[tuple[int, str, str]]:
    return sorted(import_data, key=lambda x: (x[0], x[2].lower()))


def _parse_import_lines(
    lines: list[str],
) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]], tuple[int, int]]:
    parser_state = _initialize_parser_state()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if _is_top_level_import_line(line):
            _process_import_line(i, line, stripped, parser_state)
        else:
            _process_non_import_line(i, line, stripped, parser_state)

    return (
        parser_state["import_lines"],
        parser_state["other_lines"],
        (parser_state["import_start"], parser_state["import_end"]),
    )


def _initialize_parser_state() -> dict[str, t.Any]:
    return {
        "import_lines": [],
        "other_lines": [],
        "import_start": -1,
        "import_end": -1,
    }


def _process_import_line(
    i: int,
    line: str,
    stripped: str,
    parser_state: dict[str, t.Any],
) -> None:
    if parser_state["import_start"] == -1:
        parser_state["import_start"] = i
    parser_state["import_end"] = i

    module = _extract_module_name(stripped)
    category = _get_import_category(module)
    parser_state["import_lines"].append((category, line, stripped))


def _process_non_import_line(
    i: int,
    line: str,
    stripped: str,
    parser_state: dict[str, t.Any],
) -> None:
    _categorize_non_import_line(
        i,
        line,
        stripped,
        parser_state["import_start"],
        parser_state["import_end"],
        parser_state["other_lines"],
    )


def _is_import_line(stripped: str) -> bool:
    return stripped.startswith(("import ", "from ")) and not stripped.startswith(
        "#",
    )


def _is_top_level_import_line(line: str, stripped: str | None = None) -> bool:
    if stripped is None:
        stripped = line.lstrip()
    return line == line.lstrip() and _is_import_line(stripped)


def _extract_module_name(stripped: str) -> str:
    if stripped.startswith("import "):
        return stripped.split()[1].split(".")[0]

    return stripped.split()[1]


def _categorize_non_import_line(
    i: int,
    line: str,
    stripped: str,
    import_start: int,
    import_end: int,
    other_lines: list[tuple[int, str]],
) -> None:
    if (
        import_start != -1 and import_end != -1 and i > import_end
    ) or import_start == -1:
        other_lines.append((i, line))
    elif stripped == "" and import_start <= i <= import_end:
        return
    else:
        other_lines.append((i, line))


def _rebuild_with_organized_imports(
    import_data: list[tuple[int, str, str]],
    other_lines: list[tuple[int, str]],
    import_bounds: tuple[int, int],
) -> list[str]:
    result_lines: list[str] = []
    import_start, import_end = import_bounds

    _add_lines_before_imports(result_lines, other_lines, import_start)

    _add_organized_imports(result_lines, import_data)

    _add_lines_after_imports(result_lines, other_lines, import_end)

    return result_lines


def _add_lines_before_imports(
    result_lines: list[str],
    other_lines: list[tuple[int, str]],
    import_start: int,
) -> None:
    for i, line in other_lines:
        if i < import_start:
            result_lines.append(line)


def _add_organized_imports(
    result_lines: list[str],
    import_data: list[tuple[int, str, str]],
) -> None:
    current_category = 0
    for category, line, _ in import_data:
        if result_lines and category > current_category:
            result_lines.append("")
        result_lines.append(line)
        current_category = category


def _add_lines_after_imports(
    result_lines: list[str],
    other_lines: list[tuple[int, str]],
    import_end: int,
) -> None:
    if any(i > import_end for i, _ in other_lines):
        result_lines.append("")
        for i, line in other_lines:
            if i > import_end:
                result_lines.append(line)


# ---------------------------------------------------------------------------
# diagnostics (project-wide sample of analyze_file results)
# ---------------------------------------------------------------------------


async def get_diagnostics(project_root: Path) -> dict[str, t.Any]:
    try:
        python_files = _get_python_files(project_root)
        metrics = await _analyze_file_sample(python_files[:10], project_root)
        return _build_success_diagnostics(len(python_files), metrics)
    except Exception as e:
        return _build_error_diagnostics(str(e))


def _get_python_files(project_root: Path) -> list[Path]:
    return list[t.Any](project_root.rglob("*.py"))


async def _analyze_file_sample(
    python_files: list[Path], project_root: Path
) -> dict[str, int]:
    metrics = {
        "mixed_import_files": 0,
        "total_mixed_modules": 0,
        "unused_import_files": 0,
        "total_unused_imports": 0,
        "pep8_violations": 0,
    }

    for file_path in python_files:
        file_metrics = await _analyze_single_file_metrics(file_path, project_root)
        if file_metrics:
            _update_metrics(metrics, file_metrics)

    return metrics


async def _analyze_single_file_metrics(
    file_path: Path,
    project_root: Path,
) -> dict[str, int] | None:
    try:
        analysis = await analyze_file(file_path, project_root)
        return _extract_file_metrics(analysis)
    except Exception:
        return None


def _extract_file_metrics(analysis: ImportAnalysis) -> dict[str, int]:
    return {
        "mixed_import_files": 1 if analysis.mixed_imports else 0,
        "total_mixed_modules": len(analysis.mixed_imports),
        "unused_import_files": 1 if analysis.unused_imports else 0,
        "total_unused_imports": len(analysis.unused_imports),
        "pep8_violations": len(analysis.import_violations),
    }


def _update_metrics(
    metrics: dict[str, int],
    file_metrics: dict[str, int],
) -> None:
    for key, value in file_metrics.items():
        metrics[key] += value


def _build_success_diagnostics(
    files_analyzed: int,
    metrics: dict[str, int],
) -> dict[str, t.Any]:
    return {
        "files_analyzed": files_analyzed,
        **metrics,
        "agent": "ImportOptimizationAgent",
        "capabilities": [
            "Mixed import style consolidation",
            "Unused import detection with vulture",
            "PEP 8 import organization",
            "Redundant import removal",
            "Intelligent context-aware analysis",
        ],
    }


def _build_error_diagnostics(error: str) -> dict[str, t.Any]:
    return {
        "files_analyzed": 0,
        "mixed_import_files": 0,
        "total_mixed_modules": 0,
        "unused_import_files": 0,
        "total_unused_imports": 0,
        "pep8_violations": 0,
        "agent": "ImportOptimizationAgent",
        "error": error,
    }


__all__ = [
    "ImportAnalysis",
    "analyze_file",
    "fix_import_issue",
    "get_diagnostics",
]
