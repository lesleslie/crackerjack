"""Tests for crackerjack.fixers.semantic.

Ported from tests/unit/agents/test_semantic_agent.py, keeping only the
cases that exercise real VectorStore/embedding-search logic. Cases
exercising SubAgent/coordinator dispatch (``get_supported_types``,
``can_handle``, ``SemanticAgent.__init__``, ``plan_before_action``) and
agent-instance bookkeeping (``pattern_stats``, ``semantic_insights``,
``_update_pattern_stats``) were dropped, since that machinery no longer
exists -- see the module docstring of ``crackerjack/fixers/semantic.py``
for the full kept/dropped rationale.

Unlike every prior ``crackerjack/fixers/*.py`` extraction, this module's
real logic genuinely depends on a stateful service (``VectorStore``,
SQLite-backed). Per this task's brief and CLAUDE.md's "real behavior over
mocks" testing philosophy, most tests here use a real ``VectorStore``
instance against a ``tmp_path``-backed SQLite database rather than mocking
it. Embedding generation is confirmed (see the module docstring) to be a
local, deterministic, hash-based fallback with no network access or model
download involved, so this is fast (sub-second for the whole suite) and
fully offline. ``VectorStore`` itself is only mocked/patched in the couple
of places where the original test suite explicitly tested plumbing/wiring
(``_get_vector_store`` constructing a ``VectorStore`` with the right
``config``), matching the original test's own intent.

Two pre-existing behaviors are deliberately pinned here, not "fixed":

1. ``_discover_semantic_patterns``'s per-code-element search always uses
   ``file_types=["py"]`` while ``VectorStore`` always stores file types
   with a leading dot (``".py"``), so that filter never matches anything
   -- ``related_patterns`` is therefore always empty, no matter what is
   indexed. See ``TestDiscoverSemanticPatternsFileTypeBug`` below.
2. The fallback embedding is not semantically meaningful: unrelated code
   snippets commonly score 0.7-0.85 cosine similarity. See
   ``TestFallbackEmbeddingIsNotSemantic`` below, which measures this
   directly against the real embedding service.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.fixers import semantic
from crackerjack.models.issues import Issue, IssueType, Priority
from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.ai.embeddings import EmbeddingService
from crackerjack.services.vector_store import VectorStore


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "sem-test",
        "type": IssueType.SEMANTIC_CONTEXT,
        "severity": Priority.MEDIUM,
        "message": "Analyze code patterns",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestReadFile:
    def test_read_file_success(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("def foo(): pass")
        assert semantic._read_file(f) == "def foo(): pass"

    def test_read_file_missing(self, tmp_path: Path) -> None:
        assert semantic._read_file(tmp_path / "missing.py") is None


class TestValidateSemanticIssue:
    def test_no_file_path(self) -> None:
        issue = _issue(file_path=None)
        result = semantic._validate_semantic_issue(issue)
        assert result is not None
        assert result.success is False
        assert "No file path specified" in result.remaining_issues[0]

    def test_file_not_found(self, tmp_path: Path) -> None:
        issue = _issue(file_path=str(tmp_path / "missing.py"))
        result = semantic._validate_semantic_issue(issue)
        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_valid_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")
        issue = _issue(file_path=str(test_file))
        result = semantic._validate_semantic_issue(issue)
        assert result is None


class TestSemanticConfiguration:
    def test_create_semantic_config(self) -> None:
        config = semantic._create_semantic_config()
        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.max_search_results == 10
        assert config.similarity_threshold == 0.7
        assert config.embedding_dimension == 384

    def test_get_persistent_db_path(self, tmp_path: Path) -> None:
        db_path = semantic._get_persistent_db_path(tmp_path)
        assert db_path.name == "semantic_index.db"
        assert db_path.parent.name == ".crackerjack"
        assert db_path.parent.exists()

    def test_get_vector_store_wiring(self, tmp_path: Path) -> None:
        """Pin the plumbing: `_get_vector_store` must construct `VectorStore`
        with the config as its first positional argument, matching the
        original test's own intent (`test_get_vector_store`)."""
        config = semantic._create_semantic_config()
        with patch("crackerjack.fixers.semantic.VectorStore") as mock_store:
            semantic._get_vector_store(config, tmp_path)
            mock_store.assert_called_once()
            assert mock_store.call_args[0][0] == config

    def test_get_vector_store_real(self, tmp_path: Path) -> None:
        config = semantic._create_semantic_config()
        store = semantic._get_vector_store(config, tmp_path)
        assert isinstance(store, VectorStore)
        assert store.config == config
        assert store.db_path == tmp_path / ".crackerjack" / "semantic_index.db"


class TestExtractCodeElements:
    def test_extract_ast_elements_function(self) -> None:
        content = "def calculate_total(items, tax, discount):\n    return items\n"
        elements = semantic._extract_code_elements(content)
        assert len(elements) == 1
        assert elements[0]["type"] == "function"
        assert elements[0]["name"] == "calculate_total"
        assert elements[0]["signature"] == "def calculate_total(items, tax, discount)"
        assert elements[0]["line_number"] == 1

    def test_extract_ast_elements_only_first_three_args(self) -> None:
        content = "def f(a, b, c, d, e):\n    pass\n"
        elements = semantic._extract_code_elements(content)
        assert elements[0]["signature"] == "def f(a, b, c)"

    def test_extract_ast_elements_class(self) -> None:
        content = "class MyClass(BaseA, BaseB):\n    pass\n"
        elements = semantic._extract_code_elements(content)
        assert len(elements) == 1
        assert elements[0]["type"] == "class"
        assert elements[0]["name"] == "MyClass"
        assert elements[0]["signature"] == "class MyClass(BaseA, BaseB)"

    def test_extract_ast_elements_docstring(self) -> None:
        content = 'def foo():\n    """Docstring here."""\n    pass\n'
        elements = semantic._extract_code_elements(content)
        assert elements[0]["docstring"] == "Docstring here."

    def test_extract_ast_elements_limited_to_ten(self) -> None:
        content = "\n".join(f"def f{i}(): pass" for i in range(15))
        elements = semantic._extract_code_elements(content)
        assert len(elements) == 10

    def test_extract_falls_back_to_text_on_syntax_error(self) -> None:
        content = "def broken(:\n    this is not valid python\n"
        elements = semantic._extract_code_elements(content)
        # Text-based fallback still finds the `def` line even though it
        # isn't parseable Python.
        assert any(e["name"] == "broken" for e in elements)

    def test_extract_text_elements_class(self) -> None:
        content = "class Foo:\n    pass\n"
        # Force a SyntaxError path indirectly isn't needed here; call the
        # text extractor directly to pin its own behavior.
        elements = semantic._extract_text_elements(content)
        assert elements[0]["type"] == "class"
        assert elements[0]["name"] == "Foo"


class TestGetAstName:
    def test_name_node(self) -> None:
        import ast

        tree = ast.parse("Base")
        node = tree.body[0].value  # type: ignore[attr-defined]
        assert semantic._get_ast_name(node) == "Base"

    def test_attribute_node(self) -> None:
        import ast

        tree = ast.parse("module.Base")
        node = tree.body[0].value  # type: ignore[attr-defined]
        assert semantic._get_ast_name(node) == "module.Base"

    def test_unknown_node(self) -> None:
        import ast

        tree = ast.parse("1 + 2")
        node = tree.body[0].value  # type: ignore[attr-defined]
        assert semantic._get_ast_name(node) == "Unknown"


class TestGenerateSemanticRecommendations:
    def test_no_insights_returns_general_recommendations_only(self) -> None:
        recs = semantic._generate_semantic_recommendations(
            {"related_patterns": [], "context_suggestions": []}
        )
        assert recs == semantic._get_general_semantic_recommendations()

    def test_related_patterns_adds_pattern_recommendation(self) -> None:
        insights = {
            "related_patterns": [{"element": {}, "related_code": []}],
            "context_suggestions": [],
        }
        recs = semantic._generate_semantic_recommendations(insights)
        assert "Found 1 similar code patterns across the codebase" in recs

    def test_high_similarity_triggers_dry_recommendation(self) -> None:
        insights = {
            "related_patterns": [
                {
                    "element": {},
                    "related_code": [{"similarity_score": 0.9}],
                }
            ],
            "context_suggestions": [],
        }
        recs = semantic._generate_semantic_recommendations(insights)
        assert any("DRY principle" in r for r in recs)

    def test_context_suggestions_adds_contextual_recommendation(self) -> None:
        insights = {"related_patterns": [], "context_suggestions": ["x"]}
        recs = semantic._generate_semantic_recommendations(insights)
        assert (
            "Semantic analysis revealed contextual insights for code understanding"
            in recs
        )


class TestCountHighSimilarityPatterns:
    def test_counts_only_above_threshold(self) -> None:
        related_patterns = [
            {
                "related_code": [
                    {"similarity_score": 0.9},
                    {"similarity_score": 0.5},
                    {"similarity_score": 0.81},
                ]
            }
        ]
        assert semantic._count_high_similarity_patterns(related_patterns) == 2

    def test_ignores_malformed_entries(self) -> None:
        assert semantic._count_high_similarity_patterns(["not-a-dict"]) == 0
        assert semantic._count_high_similarity_patterns([{"related_code": "bad"}]) == 0


class TestCreateSemanticErrorResult:
    def test_create_semantic_error_result(self) -> None:
        result = semantic._create_semantic_error_result(ValueError("boom"))
        assert result.success is False
        assert result.confidence == 0.0
        assert "boom" in result.remaining_issues[0]
        assert len(result.recommendations) == 3


class TestPerformSemanticAnalysis:
    """Real VectorStore against tmp_path, no mocking."""

    @pytest.fixture
    def config(self) -> SemanticConfig:
        return semantic._create_semantic_config()

    async def test_success(self, tmp_path: Path, config: SemanticConfig) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("def calculate_total(items):\n    return sum(items)\n")
        store = VectorStore(config, db_path=tmp_path / "idx.db")
        issue = _issue(file_path=str(test_file))

        result = await semantic._perform_semantic_analysis(test_file, store, issue)

        assert result.success is True
        assert result.confidence == 0.8
        assert result.files_modified == []
        assert any("Semantic analysis completed" in f for f in result.fixes_applied)

    async def test_cannot_read_file(
        self, tmp_path: Path, config: SemanticConfig
    ) -> None:
        store = VectorStore(config, db_path=tmp_path / "idx.db")
        issue = _issue(file_path=str(tmp_path / "missing.py"))

        result = await semantic._perform_semantic_analysis(
            tmp_path / "missing.py", store, issue
        )

        assert result.success is False
        assert "Could not read file" in result.remaining_issues[0]

    async def test_indexing_error_is_non_fatal(
        self, tmp_path: Path, config: SemanticConfig
    ) -> None:
        """Preserved quirk: if `vector_store.index_file` raises, the
        original agent silently continues (the `self.log(...)` warning
        call was a no-op) rather than failing the whole analysis."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass")
        store = VectorStore(config, db_path=tmp_path / "idx.db")
        issue = _issue(file_path=str(test_file))

        with patch.object(
            store, "index_file", side_effect=RuntimeError("indexing broke")
        ):
            result = await semantic._perform_semantic_analysis(test_file, store, issue)

        assert result.success is True


class TestDiscoverSemanticPatternsFileTypeBug:
    """Pins the confirmed pre-existing file_types dot-mismatch bug.

    `_discover_semantic_patterns` always searches with `file_types=["py"]`
    but `VectorStore` always stores `file_type` with a leading dot
    (`.py`), so the per-code-element search can never match anything --
    `related_patterns` is always empty regardless of what real matching
    content is indexed.
    """

    async def test_related_patterns_always_empty_despite_real_match(
        self, tmp_path: Path
    ) -> None:
        config = semantic._create_semantic_config()
        store = VectorStore(config, db_path=tmp_path / "idx.db")

        # Index a second file with the exact same function signature, so a
        # `file_types`-unfiltered search would certainly find it (self-hash
        # match => similarity 1.0, comfortably above the 0.6 threshold).
        other_file = tmp_path / "other.py"
        other_file.write_text("def calculate_total(items):\n    return items\n")
        store.index_file(other_file)

        target_file = tmp_path / "target.py"
        content = "def calculate_total(items):\n    return items\n"
        target_file.write_text(content)

        issue = _issue(file_path=str(target_file), message="")
        insights = await semantic._discover_semantic_patterns(
            store, target_file, content, issue
        )

        assert insights["related_patterns"] == []

    async def test_unfiltered_search_would_have_matched(self, tmp_path: Path) -> None:
        """Control case proving the match exists and would be found if the
        file_types filter were not mismatched -- isolates the bug to the
        filter itself, not to embedding/search logic in general."""
        config = semantic._create_semantic_config()
        store = VectorStore(config, db_path=tmp_path / "idx.db")

        other_file = tmp_path / "other.py"
        other_file.write_text("def calculate_total(items):\n    return items\n")
        store.index_file(other_file)

        query = SearchQuery(
            query="def calculate_total(items)",
            max_results=5,
            min_similarity=0.6,
            file_types=["py"],  # exactly what _discover_semantic_patterns sends
        )
        assert store.search(query) == []

        query_no_filter = SearchQuery(
            query="def calculate_total(items)",
            max_results=5,
            min_similarity=0.6,
        )
        assert len(store.search(query_no_filter)) == 1


class TestDiscoverSemanticPatternsContextSuggestions:
    async def test_context_suggestions_can_find_matches(self, tmp_path: Path) -> None:
        """Unlike related_patterns, _analyze_issue_context's SearchQuery
        does not set file_types, so it is not subject to the dot-mismatch
        bug and can genuinely find matches."""
        config = semantic._create_semantic_config()
        store = VectorStore(config, db_path=tmp_path / "idx.db")

        other_file = tmp_path / "other.py"
        other_file.write_text("Some prior semantic issue message context")
        store.index_file(other_file)

        target_file = tmp_path / "target.py"
        content = "def foo(): pass\n"
        target_file.write_text(content)

        issue = _issue(
            file_path=str(target_file),
            message="Some prior semantic issue message context",
        )
        insights = await semantic._discover_semantic_patterns(
            store, target_file, content, issue
        )

        assert len(insights["context_suggestions"]) == 1
        assert insights["context_suggestions"][0]["type"] == "similar_issues"

    async def test_insights_shape(self, tmp_path: Path) -> None:
        config = semantic._create_semantic_config()
        store = VectorStore(config, db_path=tmp_path / "idx.db")
        issue = _issue(message="")

        insights = await semantic._discover_semantic_patterns(
            store, tmp_path / "x.py", "def foo(): pass", issue
        )

        assert set(insights.keys()) == {
            "related_patterns",
            "similar_functions",
            "context_suggestions",
            "pattern_clusters",
        }
        # Preserved quirk: these two keys are never populated by any logic
        # in the original agent.
        assert insights["similar_functions"] == []
        assert insights["pattern_clusters"] == []

    async def test_empty_issue_message_skips_context_analysis(
        self, tmp_path: Path
    ) -> None:
        config = semantic._create_semantic_config()
        store = VectorStore(config, db_path=tmp_path / "idx.db")
        issue = _issue(message="")

        insights = await semantic._discover_semantic_patterns(
            store, tmp_path / "x.py", "def foo(): pass", issue
        )

        assert insights["context_suggestions"] == []


class TestAnalyzeSemanticContext:
    """End-to-end entry point, real VectorStore, real files on tmp_path."""

    async def test_no_file_path(self, tmp_path: Path) -> None:
        issue = _issue(file_path=None)
        result = await semantic.analyze_semantic_context(issue, tmp_path)
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_file_not_found(self, tmp_path: Path) -> None:
        issue = _issue(file_path=str(tmp_path / "nonexistent.py"))
        result = await semantic.analyze_semantic_context(issue, tmp_path)
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_success(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def calculate_total(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        total += item.price\n"
            "    return total\n"
        )
        issue = _issue(file_path=str(test_file), message="Analyze code patterns")

        result = await semantic.analyze_semantic_context(issue, tmp_path)

        assert result.success is True
        assert result.confidence == 0.8
        assert result.files_modified == []
        # Real db file was created under the real persistent path.
        assert (tmp_path / ".crackerjack" / "semantic_index.db").exists()

    async def test_error_handling(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        issue = _issue(file_path=str(test_file))

        with patch(
            "crackerjack.fixers.semantic._create_semantic_config",
            side_effect=Exception("Test error"),
        ):
            result = await semantic.analyze_semantic_context(issue, tmp_path)

        assert result.success is False
        assert "Test error" in result.remaining_issues[0]


class TestFallbackEmbeddingIsNotSemantic:
    """Documents (does not "fix") the fact that the fallback embedding is a
    hash of the whole input text, not a real semantic encoding: unrelated
    strings routinely score well above the similarity thresholds used
    throughout this module (0.5-0.7)."""

    def test_unrelated_snippets_score_high_similarity(self) -> None:
        config = semantic._create_semantic_config()
        svc = EmbeddingService(config)

        e1 = svc.generate_embedding("def calculate_total(items):")
        e2 = svc.generate_embedding("class Foo(Bar):")

        similarity = svc.calculate_similarity(e1, e2)

        assert similarity > 0.5

    def test_identical_text_scores_perfect_similarity(self) -> None:
        config = semantic._create_semantic_config()
        svc = EmbeddingService(config)

        e1 = svc.generate_embedding("def calculate_total(items):")
        e2 = svc.generate_embedding("def calculate_total(items):")

        assert svc.calculate_similarity(e1, e2) == 1.0
