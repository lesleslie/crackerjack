"""Deterministic VectorStore/embedding-search semantic-context analyzer.

Extracted from ``crackerjack.agents.semantic_agent.SemanticAgent`` (461
lines). Unlike every prior ``crackerjack/fixers/*.py`` extraction, this
agent's real logic is not self-contained AST/regex/string transforms -- it
genuinely depends on the service-layer ``crackerjack.services.vector_store.
VectorStore`` (SQLite-backed embedding index + cosine-similarity search) and
``crackerjack.models.semantic_models`` (``SearchQuery``/``SemanticConfig``).
Per this task's brief, that dependency chain is legitimate and is imported
directly here, not reimplemented or stubbed.

Confirmed by reading the full original source: there is no LLM/API call
anywhere in this agent or in ``VectorStore``/``EmbeddingService``. Embedding
generation (see ``crackerjack.services.ai.embeddings.EmbeddingService.
generate_embedding``) is entirely a local, deterministic SHA256-hash-derived
pseudo-embedding (``_generate_fallback_embedding``) -- the ``AutoTokenizer``/
ONNX-session machinery in that module is loaded lazily via a ``session``/
``tokenizer`` property that nothing in the actual embedding-generation or
search call path ever touches (confirmed via ``grep`` across both files: the
only callers of ``EmbeddingService.session``/``.tokenizer`` are themselves
dead). So despite ``SemanticConfig.embedding_model`` naming a
``sentence-transformers`` model, no ML model is ever loaded or downloaded by
this code path today -- everything through ``VectorStore.index_file``/
``VectorStore.search`` is pure stdlib/numpy, deterministic, and fast. This
means the "real behavior over mocks" tests in ``tests/fixers/test_semantic.py``
use a real ``VectorStore`` against a ``tmp_path``-backed SQLite file with no
network access and no slow model download.

**Important, independently-verified caveat about search quality**: because
the fallback embedding is a hash of the *entire* input text (not a true
semantic encoding), essentially any two different short code snippets
produce moderately-to-highly similar vectors (cosine similarity commonly
0.7-0.85 between totally unrelated strings, measured directly against this
codebase's actual dependencies -- see ``tests/fixers/test_semantic.py``).
The "similarity" scores this agent reports are therefore not meaningfully
semantic today. This is a pre-existing characteristic of the wider
``VectorStore``/``EmbeddingService`` layer (out of scope for this
extraction to fix), not something introduced here -- preserved verbatim.

**Confirmed pre-existing bug, preserved verbatim (not fixed), pinned by a
test**: ``_discover_semantic_patterns`` builds each per-code-element
``SearchQuery`` with ``file_types=["py"]`` (no leading dot), but
``VectorStore``/``EmbeddingService`` always store ``file_type`` as
``Path.suffix`` (WITH a leading dot, e.g. ``".py"``), and
``VectorStore._get_all_embeddings``'s SQL filter (``WHERE file_type IN
(?)``) does exact string matching. Since ``file_types=["py"]`` is hardcoded
(there is no code path that ever supplies a different value), this filter
mismatch means the per-code-element search inside ``_discover_semantic_patterns``
**always** returns zero rows -- ``related_patterns`` in the returned
insights dict is therefore always empty, no matter how much genuinely
matching content exists in the index. This bug always fires on the only
realistic input shape (per Task 14's precedent, that makes it a Critical
finding, not a Minor one) -- see this task's report for the full writeup.
By contrast, ``_analyze_issue_context``'s ``SearchQuery`` does *not* set
``file_types`` at all (defaults to ``[]``, which ``_get_all_embeddings``
treats as "no filter"), so ``context_suggestions`` genuinely can find
matches. This asymmetry -- one search path always empty, the other
functional -- is preserved exactly as in the original.

What was intentionally dropped versus the original ``SemanticAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__``,
  ``get_supported_types``, ``can_handle``, and ``agent_registry.register(...)``
  -- these only ever decided *whether* and *how confidently* this fixer
  should run for a given ``Issue``; that routing job belongs to whatever
  calls into this module now, not to the module itself.
- ``plan_before_action`` -- returns a static ``dict`` describing a strategy
  ("index file content", "discover related patterns", ...) with zero
  computation and is never invoked by anything in this codebase for
  ``SemanticAgent`` specifically (only ``ArchitectAgent.plan_before_action``
  is ever called, from ``crackerjack/agents/coordinator.py`` and
  ``crackerjack/core/proactive_workflow.py``). Same treatment as
  ``crackerjack/fixers/architecture.py`` gives its own dropped
  ``plan_before_action``.
- ``self.pattern_stats``/``self.semantic_insights`` instance state and
  ``_update_pattern_stats`` -- pure bookkeeping counters mutated after a
  successful fix but never read anywhere (not part of ``FixResult``, not
  logged, not exposed to any caller in this codebase). This is
  ``SubAgent``-instance telemetry with no external consumer, the same
  category of drop as the ``AgentContext``-derived values precedent
  ("thread through as explicit parameters if load-bearing, drop if
  cosmetic") -- these are cosmetic.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op
  ``pass`` on the base class, so these calls had no observable effect
  (same treatment as every other ``crackerjack/fixers/*.py`` extraction
  so far, e.g. ``import_optimization.py``/``security.py``). The ``except
  Exception as e:`` bindings that existed only to feed those no-op log
  calls are simplified to bare ``except Exception:``; the surrounding
  try/except control flow (catch-and-continue on indexing/search failure)
  is otherwise unchanged.
- ``AgentContext.get_file_content`` -- replaced with a direct
  ``pathlib.Path.read_text`` via ``_read_file`` below (same pattern as
  every prior extraction), dropping ``AgentContext``'s path-traversal
  check and file-size cap.
- A dead branch, preserved rather than removed: ``analyze_and_fix``
  (renamed ``analyze_semantic_context`` below) checks ``if issue.file_path
  is None`` *after* already calling ``_validate_semantic_issue``, which
  itself returns a ``FixResult`` whenever ``not issue.file_path`` (True for
  both ``None`` and ``""``). So by the time the second check is reached,
  ``issue.file_path`` can never be ``None`` -- it is unreachable dead code
  in the original, most likely present only to satisfy a type checker
  ahead of ``Path(issue.file_path)``. Kept verbatim, not removed, per
  CLAUDE.md Rule 7 ("preserve functional requirements... fix the technical
  issue, not the requirements").

Rename worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``analyze_semantic_context``
below (not ``fix_...`` -- this agent never mutates any file; ``FixResult.
files_modified`` is always ``[]``), taking an explicit ``project_path:
Path`` parameter in place of ``self.context.project_path``.

This agent has no subprocess-invoking helpers at all (no ``self.run_command``,
no ``subprocess`` import anywhere in the original file) -- nothing to add to
Task 22a's cwd-pinning file list from this extraction.

There is also no ``FixPlan``/``ChangeSpec`` applicator (``execute_fix_plan``)
in the original agent -- not invented here, per the plan's own instruction
not to add one where the source has none.

Also preserved verbatim: two keys in the ``_discover_semantic_patterns``
insights dict -- ``"similar_functions"`` and ``"pattern_clusters"`` -- are
initialized to empty lists but never populated by any logic anywhere in the
original file. They are inert placeholders for an unimplemented feature, not
something this extraction should invent logic for.
"""

from __future__ import annotations

import ast
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue
from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.vector_store import VectorStore


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (Exception, OSError):
        return None


def _validate_semantic_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path specified for semantic analysis"],
        )

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )

    return None


def _create_semantic_config() -> SemanticConfig:
    return SemanticConfig(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        chunk_size=512,
        chunk_overlap=50,
        max_search_results=10,
        similarity_threshold=0.7,
        embedding_dimension=384,
    )


def _get_persistent_db_path(project_path: Path) -> Path:
    db_path = project_path / ".crackerjack" / "semantic_index.db"
    db_path.parent.mkdir(exist_ok=True)
    return db_path


def _get_vector_store(config: SemanticConfig, project_path: Path) -> VectorStore:
    db_path = _get_persistent_db_path(project_path)
    return VectorStore(config, db_path=db_path)


def _extract_docstring_from_node(node: t.Any) -> str:
    if not node.body or not isinstance(node.body[0], ast.Expr):
        return ""

    value = node.body[0].value
    if hasattr(value, "s"):
        return str(value.s)[:100]
    if hasattr(value, "value") and isinstance(value.value, str):
        return str(value.value)[:100]
    return ""


def _build_function_signature(node: t.Any) -> str:
    signature = f"def {node.name}("
    if node.args.args:
        args = [arg.arg for arg in node.args.args[:3]]
        signature += ", ".join(args)
    signature += ")"
    return signature


def _build_class_signature(node: t.Any) -> str:
    signature = f"class {node.name}"
    if node.bases:
        bases = [_get_ast_name(base) for base in node.bases[:2]]
        signature += f"({', '.join(bases)})"
    return signature


def _get_ast_name(node: t.Any) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_ast_name(node.value)}.{node.attr}"
    return "Unknown"


def _extract_ast_elements(content: str) -> list[dict[str, t.Any]]:
    class _CodeElementExtractor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.elements: list[dict[str, t.Any]] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.elements.append(
                {
                    "type": "function",
                    "name": node.name,
                    "signature": _build_function_signature(node),
                    "docstring": _extract_docstring_from_node(node),
                    "line_number": node.lineno,
                },
            )
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.elements.append(
                {
                    "type": "class",
                    "name": node.name,
                    "signature": _build_class_signature(node),
                    "line_number": node.lineno,
                },
            )
            self.generic_visit(node)

    tree = ast.parse(content)
    extractor = _CodeElementExtractor()
    extractor.visit(tree)
    return extractor.elements[:10]


def _extract_text_elements(content: str) -> list[dict[str, t.Any]]:
    elements = []
    lines = content.split("\n")
    for i, line in enumerate(lines[:50]):
        stripped = line.strip()
        if stripped.startswith("def ") and "(" in stripped:
            func_name = stripped.split("(")[0].replace("def ", "").strip()
            elements.append(
                {
                    "type": "function",
                    "name": func_name,
                    "signature": stripped,
                    "line_number": i + 1,
                },
            )
        elif stripped.startswith("class ") and ":" in stripped:
            class_name = stripped.split(":")[0].replace("class ", "").strip()
            elements.append(
                {
                    "type": "class",
                    "name": class_name,
                    "signature": stripped,
                    "line_number": i + 1,
                },
            )
    return elements


def _extract_code_elements(content: str) -> list[dict[str, t.Any]]:
    try:
        return _extract_ast_elements(content)
    except SyntaxError:
        return _extract_text_elements(content)


async def _analyze_issue_context(
    vector_store: VectorStore,
    issue: Issue,
) -> list[dict[str, t.Any]]:
    suggestions = []

    search_query = SearchQuery(
        query=issue.message,
        max_results=5,
        min_similarity=0.5,
    )

    with suppress(Exception):
        results = vector_store.search(search_query)
        if results:
            suggestions.append(
                {
                    "type": "similar_issues",
                    "description": f"Found {len(results)} similar patterns in codebase",
                    "examples": [
                        {
                            "file": str(result.file_path.name),
                            "content": result.content[:150],
                            "similarity": result.similarity_score,
                        }
                        for result in results[:3]
                    ],
                },
            )

    return suggestions


async def _discover_semantic_patterns(
    vector_store: VectorStore,
    file_path: Path,
    content: str,
    issue: Issue,
) -> dict[str, t.Any]:
    insights: dict[str, t.Any] = {
        "related_patterns": [],
        "similar_functions": [],
        "context_suggestions": [],
        "pattern_clusters": [],
    }

    code_elements = _extract_code_elements(content)

    for element in code_elements:
        search_query = SearchQuery(
            query=element["signature"],
            max_results=5,
            min_similarity=0.6,
            file_types=["py"],
        )

        with suppress(Exception):
            results = vector_store.search(search_query)
            if results:
                related_results = [
                    result for result in results if result.file_path != file_path
                ]

                if related_results:
                    insights["related_patterns"].append(
                        {
                            "element": element,
                            "related_code": [
                                {
                                    "file_path": str(result.file_path),
                                    "content": result.content[:200],
                                    "similarity_score": result.similarity_score,
                                    "lines": f"{result.start_line}-{result.end_line}",
                                }
                                for result in related_results[:3]
                            ],
                        },
                    )

    if issue.message:
        issue_insights = await _analyze_issue_context(vector_store, issue)
        insights["context_suggestions"].extend(issue_insights)

    return insights


def _count_high_similarity_patterns(related_patterns: list[t.Any]) -> int:
    high_similarity_count = 0

    for pattern in related_patterns:
        if not isinstance(pattern, dict):
            continue
        related_code = pattern.get("related_code", [])
        if not isinstance(related_code, list):
            continue
        for code in related_code:
            if isinstance(code, dict) and code.get("similarity_score", 0) > 0.8:
                high_similarity_count += 1

    return high_similarity_count


def _analyze_related_patterns(related_patterns: list[t.Any]) -> list[str]:
    recommendations = []

    recommendations.append(
        f"Found {len(related_patterns)} similar code patterns across the codebase",
    )

    high_similarity_count = _count_high_similarity_patterns(related_patterns)
    if high_similarity_count > 0:
        recommendations.append(
            f"Detected {high_similarity_count} highly similar implementations - "
            "consider refactoring for DRY principle compliance",
        )

    return recommendations


def _get_general_semantic_recommendations() -> list[str]:
    return [
        "Consider semantic indexing of related modules for better code discovery",
        "Review similar patterns for consistency in naming and implementation",
        "Use semantic search to discover reusable components before implementing new ones",
    ]


def _generate_semantic_recommendations(
    insights: dict[str, t.Any],
) -> list[str]:
    recommendations = []

    related_patterns = insights.get("related_patterns", [])
    context_suggestions = insights.get("context_suggestions", [])

    if related_patterns:
        recommendations.extend(_analyze_related_patterns(related_patterns))

    if context_suggestions:
        recommendations.append(
            "Semantic analysis revealed contextual insights for code understanding",
        )

    recommendations.extend(_get_general_semantic_recommendations())

    return recommendations


def _create_semantic_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Semantic analysis failed: {error}"],
        recommendations=[
            "Ensure semantic search index is properly initialized",
            "Check if file contains valid code for analysis",
            "Verify semantic search configuration is correct",
        ],
    )


async def _perform_semantic_analysis(
    file_path: Path,
    vector_store: VectorStore,
    issue: Issue,
) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    with suppress(Exception):
        vector_store.index_file(file_path)

    semantic_insights = await _discover_semantic_patterns(
        vector_store,
        file_path,
        content,
        issue,
    )

    recommendations = _generate_semantic_recommendations(semantic_insights)

    return FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=[
            f"Semantic analysis completed for {file_path.name}",
            f"Discovered {len(semantic_insights.get('related_patterns', []))} related patterns",
            f"Generated {len(recommendations)} semantic recommendations",
        ],
        recommendations=recommendations,
        files_modified=[],
    )


async def analyze_semantic_context(issue: Issue, project_path: Path) -> FixResult:
    validation_result = _validate_semantic_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided for semantic analysis"],
        )

    file_path = Path(issue.file_path)

    try:
        config = _create_semantic_config()
        vector_store = _get_vector_store(config, project_path)

        return await _perform_semantic_analysis(
            file_path,
            vector_store,
            issue,
        )

    except Exception as e:
        return _create_semantic_error_result(e)


__all__ = [
    "analyze_semantic_context",
]
