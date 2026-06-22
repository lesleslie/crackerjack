"""Tests for DocstringEnricher (Task 10) — RED first."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestEnricherDetectsMissingDocstring:
    def test_enricher_detects_missing_docstring(self, tmp_path: Path) -> None:
        """Function with no docstring is flagged as needing enrichment."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                return x + y
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        enricher = DocstringEnricher()
        candidates = enricher.scan_for_candidates(src_file)

        assert len(candidates) == 1
        assert candidates[0].name == "add"
        assert candidates[0].needs_enrichment is True


@pytest.mark.unit
class TestEnricherDetectsThinDocstring:
    def test_enricher_detects_thin_docstring(self, tmp_path: Path) -> None:
        """Docstring under 3 lines or lacking Args: section is flagged."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                \"\"\"Add two numbers.\"\"\"
                return x + y
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        enricher = DocstringEnricher()
        candidates = enricher.scan_for_candidates(src_file)

        assert len(candidates) == 1
        assert candidates[0].needs_enrichment is True


@pytest.mark.unit
class TestEnricherSkipsPrivateMethods:
    def test_enricher_skips_private_methods(self, tmp_path: Path) -> None:
        """Methods starting with _ are not included in candidates."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            class Foo:
                def _private(self) -> None:
                    pass

                def public(self) -> None:
                    pass
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        enricher = DocstringEnricher()
        candidates = enricher.scan_for_candidates(src_file)

        names = [c.name for c in candidates]
        assert "_private" not in names
        assert any("public" in n for n in names)


@pytest.mark.unit
class TestEnricherWritesBackHighConfidence:
    async def test_enricher_writes_back_high_confidence(
        self, tmp_path: Path
    ) -> None:
        """confidence >= 0.8 → source file is modified with new docstring."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                return x + y
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        enricher = DocstringEnricher()

        mock_response = {
            "docstring": "Add two integers.\n\nArgs:\n    x: First operand.\n    y: Second operand.\n\nReturns:\n    Sum of x and y.",
            "confidence": 0.92,
        }
        with patch.object(enricher, "_call_llm", new=AsyncMock(return_value=[mock_response])):
            result = await enricher.enrich(src_file)

        assert result.enriched == 1
        assert result.skipped == 0
        updated = src_file.read_text()
        assert "Add two integers" in updated


@pytest.mark.unit
class TestEnricherSkipsLowConfidence:
    async def test_enricher_skips_low_confidence(self, tmp_path: Path) -> None:
        """confidence < 0.8 → added to report_only, source unchanged."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                return x + y
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)
        original = src_file.read_text()

        enricher = DocstringEnricher()

        mock_response = {
            "docstring": "Add numbers.",
            "confidence": 0.5,
        }
        with patch.object(enricher, "_call_llm", new=AsyncMock(return_value=[mock_response])):
            result = await enricher.enrich(src_file)

        assert result.enriched == 0
        assert len(result.report_only) >= 1
        assert src_file.read_text() == original


@pytest.mark.unit
class TestEnricherPreservesSourceFormatting:
    async def test_enricher_preserves_source_formatting(
        self, tmp_path: Path
    ) -> None:
        """libcst rewrite doesn't alter surrounding code indentation or comments."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        source = textwrap.dedent("""\
            # top-level comment
            class Foo:
                # class comment
                def bar(self) -> None:
                    pass
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        enricher = DocstringEnricher()
        mock_response = {
            "docstring": "Do bar.\n\nArgs:\n    None.\n\nReturns:\n    None.",
            "confidence": 0.9,
        }
        with patch.object(enricher, "_call_llm", new=AsyncMock(return_value=[mock_response])):
            await enricher.enrich(src_file)

        updated = src_file.read_text()
        assert "# top-level comment" in updated
        assert "# class comment" in updated


@pytest.mark.unit
class TestEnricherBatchCallsReduceLLMRoundTrips:
    async def test_enricher_batch_calls_reduce_llm_round_trips(
        self, tmp_path: Path
    ) -> None:
        """10 functions → at most 1 LLM call (batch size 10)."""
        from crackerjack.documentation.docstring_enricher import DocstringEnricher

        funcs = "\n".join(
            f"def func_{i}(x: int) -> int:\n    return x + {i}\n"
            for i in range(10)
        )
        src_file = tmp_path / "module.py"
        src_file.write_text(funcs)

        call_count = 0

        async def mock_llm(candidates):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            return [
                {"docstring": f"Do func_{i}.\n\nArgs:\n    x: Input.\n\nReturns:\n    int.", "confidence": 0.9}
                for i in range(len(candidates))
            ]

        enricher = DocstringEnricher()
        with patch.object(enricher, "_call_llm", new=mock_llm):
            await enricher.enrich(src_file)

        assert call_count <= 1, f"Expected ≤1 LLM call for 10 functions, got {call_count}"


@pytest.mark.unit
class TestDocsCheckFailsWhenNoZensicalToml:
    def test_docs_check_fails_when_no_zensical_toml(self, tmp_path: Path) -> None:
        """docs check returns False when zensical.toml is absent."""
        from crackerjack.documentation.docstring_enricher import check_docs_quality

        result = check_docs_quality(tmp_path)
        assert result.zensical_toml_present is False
        assert result.passed is False


@pytest.mark.unit
class TestDocsCheckReportsCoveragePercentage:
    def test_docs_check_reports_coverage_percentage(self, tmp_path: Path) -> None:
        """docs check returns count of documented vs total public APIs."""
        from crackerjack.documentation.docstring_enricher import (
            DocstringEnricher,
            check_docs_quality,
        )

        source = textwrap.dedent("""\
            def documented(x: int) -> int:
                \"\"\"Well-documented function.

                Args:
                    x: Input value.

                Returns:
                    The value unchanged.
                \"\"\"
                return x

            def undocumented(x: int) -> int:
                return x
        """)
        src_file = tmp_path / "module.py"
        src_file.write_text(source)
        (tmp_path / "zensical.toml").write_text("[project]\nsite_name = 'Test'\n")

        result = check_docs_quality(tmp_path)
        assert result.total_public_apis >= 2
        assert result.documented_apis >= 1
        assert 0.0 <= result.coverage_pct <= 1.0
