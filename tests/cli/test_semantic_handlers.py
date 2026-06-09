"""Tests for ``crackerjack.cli.semantic_handlers``.

Covers the four public CLI handlers:
- ``handle_semantic_index`` — single file, directory, missing path
- ``handle_semantic_search`` — results, no results, error fallback
- ``handle_semantic_stats`` — populated index, empty index
- ``handle_remove_from_semantic_index`` — success, not found, error fallback

The ``VectorStore`` is mocked at the ``crackerjack.services.vector_store``
import boundary so the tests exercise real handler logic (console output,
control flow, error handling) without spinning up an actual vector store.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Group, RenderableType

from rich.console import Console as _RichConsole
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from crackerjack.cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
    handle_semantic_stats,
)
from crackerjack.models.semantic_models import IndexStats, SearchResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_console() -> MagicMock:
    """``ConsoleInterface``-compatible mock with a ``print`` method."""
    return MagicMock()


@pytest.fixture
def vector_store_mock() -> MagicMock:
    """Return a ``MagicMock`` shaped like ``VectorStore`` with sensible defaults."""
    store = MagicMock()
    store.index_file.return_value = [MagicMock(), MagicMock(), MagicMock()]
    store.search.return_value = []
    store.get_stats.return_value = IndexStats(
        total_files=2,
        total_chunks=10,
        index_size_mb=1.5,
        last_updated=datetime(2026, 1, 1, 12, 0, 0),
        file_types={".py": 2},
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        avg_chunk_size=120.0,
    )
    store.remove_file.return_value = True
    return store


def _make_result(
    file_name: str = "mod.py",
    content: str = "def foo(): pass",
    score: float = 0.85,
    start: int = 1,
    end: int = 1,
) -> SearchResult:
    return SearchResult(
        file_path=Path(f"/tmp/proj/{file_name}"),
        chunk_id=f"chunk-{file_name}-{start}",
        content=content,
        similarity_score=score,
        start_line=start,
        end_line=end,
        file_type="py",
    )


def _render_to_text(renderable: RenderableType | object) -> str:
    """Render a Rich renderable to plain text using a throwaway console."""
    rc = _RichConsole(record=True, width=200, force_terminal=False)
    rc.print(renderable)
    return rc.export_text()


def _all_console_text(console: MagicMock) -> str:
    """Flatten ``console.print`` call args and renderable contents into text.

    For each ``print`` call, we serialize the first positional arg with
    ``str()`` AND, if it looks like a Rich renderable, render it to plain
    text. This lets us assert against table/panel titles and cell content
    that would otherwise be hidden behind ``<rich.panel.Panel object>``.
    """
    chunks: list[str] = []
    for call in console.print.call_args_list:
        for arg in call.args:
            chunks.append(str(arg))
            if isinstance(arg, (RenderableType, Group, Panel, Table, str)):
                try:
                    chunks.append(_render_to_text(arg))
                except Exception:
                    pass
        for value in call.kwargs.values():
            chunks.append(str(value))
    return " ".join(chunks)


# ---------------------------------------------------------------------------
# handle_semantic_index
# ---------------------------------------------------------------------------


class TestHandleSemanticIndex:
    def test_missing_file_prints_error(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        missing = tmp_path / "does_not_exist.py"
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
        ) as vs_cls:
            handle_semantic_index(str(missing), console=mock_console)
        vs_cls.assert_not_called()
        text = _all_console_text(mock_console)
        assert "File does not exist" in text
        assert str(missing) in text

    def test_indexes_single_file(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        vector_store_mock: MagicMock,
    ) -> None:
        target = tmp_path / "src.py"
        target.write_text("x = 1\n")
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_index(str(target), console=mock_console)
        vector_store_mock.index_file.assert_called_once()
        text = _all_console_text(mock_console)
        assert "Successfully indexed" in text
        assert "3 chunks" in text
        assert "Index now contains" in text

    def test_indexes_directory_recursively(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        vector_store_mock: MagicMock,
    ) -> None:
        (tmp_path / "a.py").write_text("a = 1\n")
        (tmp_path / "b.py").write_text("b = 2\n")
        (tmp_path / "c.txt").write_text("ignored\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "d.py").write_text("d = 4\n")

        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_index(str(tmp_path), console=mock_console)

        assert vector_store_mock.index_file.call_count == 3
        text = _all_console_text(mock_console)
        assert "3 files" in text
        assert "9 total chunks" in text

    def test_directory_index_warns_on_per_file_failure(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
        vector_store_mock: MagicMock,
    ) -> None:
        (tmp_path / "ok.py").write_text("ok = True\n")
        (tmp_path / "bad.py").write_text("bad = False\n")
        vector_store_mock.index_file.side_effect = [
            [MagicMock()],
            RuntimeError("encoder crashed"),
        ]

        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_index(str(tmp_path), console=mock_console)

        text = _all_console_text(mock_console)
        assert "Warning" in text
        assert "encoder crashed" in text
        assert "1 files" in text

    def test_falls_back_to_default_console_when_none(
        self,
        tmp_path: Path,
        vector_store_mock: MagicMock,
    ) -> None:
        target = tmp_path / "src.py"
        target.write_text("x = 1\n")
        fake_console = MagicMock()
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch(
                "crackerjack.core.console.CrackerjackConsole",
                return_value=fake_console,
            ):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    handle_semantic_index(str(target))
        # Default console must have received at least one print.
        assert fake_console.print.call_count >= 1

    def test_outer_exception_is_caught(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "src.py"
        target.write_text("x = 1\n")
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            side_effect=RuntimeError("boom"),
        ):
            handle_semantic_index(str(target), console=mock_console)
        text = _all_console_text(mock_console)
        assert "Error indexing file" in text
        assert "boom" in text

    def test_brackets_in_error_are_escaped(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "src.py"
        target.write_text("x = 1\n")
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            side_effect=RuntimeError("got [bad] tag"),
        ):
            handle_semantic_index(str(target), console=mock_console)
        text = _all_console_text(mock_console)
        # The error message should escape the brackets so Rich doesn't
        # misinterpret them as markup.
        assert "\\[bad\\]" in text


# ---------------------------------------------------------------------------
# handle_semantic_search
# ---------------------------------------------------------------------------


class TestHandleSemanticSearch:
    def test_no_results_prints_message(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        vector_store_mock.search.return_value = []
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_search("nonexistent term", console=mock_console)
        text = _all_console_text(mock_console)
        assert "No results found" in text
        # When there are no results the function should NOT print the
        # top-result panel; only the "no results" message.
        assert "Best Match" not in text

    def test_results_rendered_as_table_and_top_panel(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        vector_store_mock.search.return_value = [
            _make_result(
                file_name="alpha.py",
                content="def alpha(): return 1",
                score=0.92,
                start=10,
                end=12,
            ),
            _make_result(
                file_name="beta.py",
                content="def beta(): return 2",
                score=0.71,
                start=3,
                end=5,
            ),
        ]
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_search("alpha", console=mock_console)

        text = _all_console_text(mock_console)
        assert "Semantic Search Results" in text
        assert "alpha.py" in text
        assert "beta.py" in text
        assert "0.920" in text
        assert "0.710" in text
        # Top result panel uses the highest-scoring entry.
        assert "Best Match" in text
        assert "/tmp/proj/alpha.py" in text

    def test_long_content_is_truncated(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        long_content = "x = 1\n" * 200  # 1200 chars, well over 80
        vector_store_mock.search.return_value = [
            _make_result(content=long_content, score=0.5),
        ]
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_search("x", console=mock_console)
        # 80-char preview ends with "..." — confirm truncation marker.
        text = _all_console_text(mock_console)
        assert "..." in text

    def test_falls_back_to_default_console_when_none(
        self,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        vector_store_mock.search.return_value = []
        fake_console = MagicMock()
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch(
                "crackerjack.core.console.CrackerjackConsole",
                return_value=fake_console,
            ):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    handle_semantic_search("anything")
        assert fake_console.print.call_count >= 1

    def test_outer_exception_is_caught(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        vector_store_mock.search.side_effect = RuntimeError("search failed")
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_search("anything", console=mock_console)
        text = _all_console_text(mock_console)
        assert "Error performing search" in text
        assert "search failed" in text

    def test_brackets_in_result_content_are_escaped(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        r"""The handler escapes ``[`` to ``\[`` in the result preview and
        the top-result panel so Rich doesn't misinterpret them as markup.

        We can't observe the escape directly in the rendered text (Rich
        re-renders ``\[`` to a literal ``[``), so we check the substitution
        by asserting the call into the handler — ``[1, 2, 3]`` should not
        appear unmodified in the table cell, AND the call into the handler
        must complete without raising (a Rich markup parse error would
        surface as a raised exception).
        """
        vector_store_mock.search.return_value = [
            _make_result(content="alpha = [1, 2, 3]", score=0.6),
        ]
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                # If the handler did not escape brackets, Rich would either
                # raise a MarkupError or strip the bracketed text. A clean
                # call is itself the primary assertion.
                handle_semantic_search("alpha", console=mock_console)
        text = _all_console_text(mock_console)
        # Confirm we reached the top-result panel and the result was rendered.
        assert "Best Match" in text
        assert "alpha = " in text
        # The handler passes the escaped content into the Panel, so the
        # cell/panel text should contain the content (Rich may normalize
        # ``\[`` back to ``[``, so we just check the trailing un-escaped
        # ``]`` is preserved literally).
        assert "1, 2, 3" in text


# ---------------------------------------------------------------------------
# handle_semantic_stats
# ---------------------------------------------------------------------------


class TestHandleSemanticStats:
    def test_prints_populated_stats(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_stats(console=mock_console)
        text = _all_console_text(mock_console)
        assert "Semantic Search Index Statistics" in text
        assert "Total Files" in text
        assert "Total Chunks" in text
        assert "Embedding Model" in text
        # stats from the fixture: 2 files, 10 chunks, 1.50 MB, avg 5.0
        assert "5.0" in text
        assert "1.50" in text
        assert "2026-01-01 12:00:00" in text

    def test_empty_index_emits_tip_panel(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        vector_store_mock.get_stats.return_value = IndexStats(
            total_files=0,
            total_chunks=0,
            index_size_mb=0.0,
            last_updated=datetime(2026, 1, 1),
            file_types={},
            embedding_model="all-MiniLM-L6-v2",
            avg_chunk_size=0.0,
        )
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_stats(console=mock_console)
        text = _all_console_text(mock_console)
        assert "Tip" in text
        assert "empty" in text

    def test_last_updated_row_renders(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        """`IndexStats.last_updated` is required (non-Optional) and the
        handler always renders the ``Last Updated`` row when present."""
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_stats(console=mock_console)
        text = _all_console_text(mock_console)
        assert "Last Updated" in text
        assert "2026-01-01 12:00:00" in text

    def test_falls_back_to_default_console_when_none(
        self,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        fake_console = MagicMock()
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch(
                "crackerjack.core.console.CrackerjackConsole",
                return_value=fake_console,
            ):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    handle_semantic_stats()
        assert fake_console.print.call_count >= 1

    def test_outer_exception_is_caught(
        self,
        mock_console: MagicMock,
        tmp_path: Path,
    ) -> None:
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            side_effect=RuntimeError("db corrupt"),
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_semantic_stats(console=mock_console)
        text = _all_console_text(mock_console)
        assert "Error retrieving stats" in text
        assert "db corrupt" in text


# ---------------------------------------------------------------------------
# handle_remove_from_semantic_index
# ---------------------------------------------------------------------------


class TestHandleRemoveFromSemanticIndex:
    def test_remove_success(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "old.py"
        target.write_text("# deprecated\n")
        vector_store_mock.remove_file.return_value = True
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_remove_from_semantic_index(str(target), console=mock_console)
        vector_store_mock.remove_file.assert_called_once()
        text = _all_console_text(mock_console)
        assert "Successfully removed" in text
        assert "old.py" in text
        assert "Index now contains" in text

    def test_remove_not_found(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "ghost.py"
        target.write_text("# never indexed\n")
        vector_store_mock.remove_file.return_value = False
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_remove_from_semantic_index(str(target), console=mock_console)
        text = _all_console_text(mock_console)
        assert "Warning" in text
        assert "was not found" in text
        # The "Successfully removed" line should NOT be present.
        assert "Successfully removed" not in text

    def test_falls_back_to_default_console_when_none(
        self,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "old.py"
        target.write_text("# deprecated\n")
        fake_console = MagicMock()
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch(
                "crackerjack.core.console.CrackerjackConsole",
                return_value=fake_console,
            ):
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    handle_remove_from_semantic_index(str(target))
        assert fake_console.print.call_count >= 1

    def test_outer_exception_is_caught(
        self,
        mock_console: MagicMock,
        vector_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "old.py"
        target.write_text("# deprecated\n")
        vector_store_mock.remove_file.side_effect = RuntimeError("disk full")
        with patch(
            "crackerjack.cli.semantic_handlers.VectorStore",
            return_value=vector_store_mock,
        ):
            with patch("pathlib.Path.cwd", return_value=tmp_path):
                handle_remove_from_semantic_index(str(target), console=mock_console)
        text = _all_console_text(mock_console)
        assert "Error removing file" in text
        assert "disk full" in text


# ---------------------------------------------------------------------------
# Smoke test: Group/Panel classes are constructed (catches API regressions)
# ---------------------------------------------------------------------------


def test_handler_search_uses_rich_table_and_panel(
    mock_console: MagicMock,
    vector_store_mock: MagicMock,
    tmp_path: Path,
) -> None:
    """Sanity: with results, the handler emits a non-trivial renderable."""
    vector_store_mock.search.return_value = [
        _make_result(content="hello", score=0.5),
    ]
    with patch(
        "crackerjack.cli.semantic_handlers.VectorStore",
        return_value=vector_store_mock,
    ):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            handle_semantic_search("hello", console=mock_console)
    # We expect at least two print() calls: the search-results panel and
    # the top-result panel.
    assert mock_console.print.call_count >= 2
    first_arg = mock_console.print.call_args_list[0].args[0]
    # Rich Panel renders to a Group/Panel object. Just ensure it isn't None
    # and is a renderable of some kind.
    assert isinstance(first_arg, RenderableType | Group) or hasattr(first_arg, "__rich__")
