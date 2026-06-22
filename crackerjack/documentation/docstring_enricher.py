from __future__ import annotations

import ast
import asyncio
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from oneiric.core.logging import get_logger

logger = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.8
BATCH_SIZE = 10


@dataclass
class DocCandidate:
    name: str
    node_type: str  # "function" | "method" | "class"
    lineno: int
    source_snippet: str
    needs_enrichment: bool = True


@dataclass
class EnrichmentResult:
    enriched: int = 0
    skipped: int = 0
    report_only: list[str] = field(default_factory=list)


@dataclass
class DocsQualityResult:
    zensical_toml_present: bool = False
    total_public_apis: int = 0
    documented_apis: int = 0
    coverage_pct: float = 0.0
    passed: bool = False


def _is_thin(docstring: str | None) -> bool:
    if not docstring:
        return True
    lines = [ln for ln in docstring.strip().splitlines() if ln.strip()]
    return len(lines) < 3 or "Args:" not in docstring


def _is_private(name: str) -> bool:
    return name.startswith("_")


def _source_snippet(source_lines: list[str], lineno: int, end_lineno: int) -> str:
    return "".join(source_lines[lineno - 1 : end_lineno])[:500]


class DocstringEnricher:
    async def enrich(self, path: Path) -> EnrichmentResult:
        result = EnrichmentResult()
        source = path.read_text(encoding="utf-8")
        candidates = self.scan_for_candidates(path)
        needs = [c for c in candidates if c.needs_enrichment]

        if not needs:
            return result

        for batch_start in range(0, len(needs), BATCH_SIZE):
            batch = needs[batch_start : batch_start + BATCH_SIZE]
            responses = await self._call_llm(batch)
            for candidate, resp in zip(batch, responses):
                confidence = resp.get("confidence", 0.0)
                docstring = resp.get("docstring", "")
                if confidence >= CONFIDENCE_THRESHOLD and docstring:
                    try:
                        source = _insert_docstring(source, candidate, docstring)
                        result.enriched += 1
                    except Exception:
                        logger.exception("libcst rewrite failed for %s", candidate.name)
                        result.skipped += 1
                        result.report_only.append(candidate.name)
                else:
                    result.skipped += 1
                    result.report_only.append(candidate.name)

        path.write_text(source, encoding="utf-8")
        return result

    def scan_for_candidates(self, path: Path) -> list[DocCandidate]:
        source = path.read_text(encoding="utf-8")
        source_lines = source.splitlines(keepends=True)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        candidates: list[DocCandidate] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if _is_private(node.name):
                    continue
                ds = ast.get_docstring(node)
                end = getattr(node, "end_lineno", node.lineno)
                candidates.append(
                    DocCandidate(
                        name=node.name,
                        node_type="class",
                        lineno=node.lineno,
                        source_snippet=_source_snippet(source_lines, node.lineno, end),
                        needs_enrichment=_is_thin(ds),
                    )
                )
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if _is_private(item.name):
                            continue
                        item_ds = ast.get_docstring(item)
                        item_end = getattr(item, "end_lineno", item.lineno)
                        candidates.append(
                            DocCandidate(
                                name=f"{node.name}.{item.name}",
                                node_type="method",
                                lineno=item.lineno,
                                source_snippet=_source_snippet(
                                    source_lines, item.lineno, item_end
                                ),
                                needs_enrichment=_is_thin(item_ds),
                            )
                        )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_private(node.name):
                    continue
                parent_is_class = False
                for other in ast.walk(tree):
                    if isinstance(other, ast.ClassDef):
                        for item in other.body:
                            if item is node:
                                parent_is_class = True
                if parent_is_class:
                    continue
                ds = ast.get_docstring(node)
                end = getattr(node, "end_lineno", node.lineno)
                candidates.append(
                    DocCandidate(
                        name=node.name,
                        node_type="function",
                        lineno=node.lineno,
                        source_snippet=_source_snippet(source_lines, node.lineno, end),
                        needs_enrichment=_is_thin(ds),
                    )
                )

        return candidates

    async def _call_llm(self, candidates: list[DocCandidate]) -> list[dict]:
        # Stub: real implementation calls MiniMax M3 via cloud worker config.
        # Returns list of {"docstring": str, "confidence": float} per candidate.
        return [{"docstring": "", "confidence": 0.0} for _ in candidates]


def check_docs_quality(repo_root: Path) -> DocsQualityResult:
    result = DocsQualityResult()
    result.zensical_toml_present = (repo_root / "zensical.toml").exists()

    py_files = list(repo_root.rglob("*.py"))
    enricher = DocstringEnricher()
    total = 0
    documented = 0

    for py_file in py_files:
        if "__pycache__" in str(py_file):
            continue
        candidates = enricher.scan_for_candidates(py_file)
        for c in candidates:
            total += 1
            if not c.needs_enrichment:
                documented += 1

    result.total_public_apis = total
    result.documented_apis = documented
    result.coverage_pct = documented / total if total > 0 else 0.0
    result.passed = result.zensical_toml_present
    return result


class _DocstringInserter(cst.CSTTransformer):
    def __init__(self, target_name: str, docstring: str) -> None:
        self._target = target_name
        self._docstring = docstring
        self._in_class: str | None = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._in_class = node.name.value
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self._in_class = None
        return updated_node

    def _make_docstring_statement(self, text: str) -> cst.SimpleStatementLine:
        dedented = textwrap.dedent(text).strip()
        # Build the node directly — parse_statement chokes on multiline strings
        return cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(f'"""{dedented}"""'))]
        )

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        fn_name = original_node.name.value
        qualified = f"{self._in_class}.{fn_name}" if self._in_class else fn_name
        # Match by qualified name OR simple name (for top-level functions)
        matches = qualified == self._target or (
            self._in_class is None and fn_name == self._target
        )
        if not matches:
            return updated_node

        body = updated_node.body
        if not isinstance(body, cst.IndentedBlock):
            return updated_node

        first = body.body[0] if body.body else None
        already_has = (
            isinstance(first, cst.SimpleStatementLine)
            and first.body
            and isinstance(first.body[0], cst.Expr)
            and isinstance(
                first.body[0].value,
                (cst.ConcatenatedString, cst.FormattedString, cst.SimpleString),
            )
        )
        if already_has:
            return updated_node

        doc_stmt = self._make_docstring_statement(self._docstring)
        new_body = cst.IndentedBlock(body=(doc_stmt, *body.body))
        return updated_node.with_changes(body=new_body)


def _insert_docstring(source: str, candidate: DocCandidate, docstring: str) -> str:
    try:
        tree = cst.parse_module(source)
        transformer = _DocstringInserter(candidate.name, docstring)
        new_tree = tree.visit(transformer)
        return new_tree.code
    except Exception:
        logger.exception("libcst failed for %s, skipping", candidate.name)
        return source
