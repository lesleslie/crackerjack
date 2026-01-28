import pytest
from unittest.mock import Mock, patch, MagicMock
from crackerjack.cli.cache_handlers import (
    handle_clear_cache,
    handle_cache_stats,
    _create_cache_stats_table,
    _populate_cache_stats_table,
    _get_hit_rate_style,
    _add_cache_totals_row,
    _display_performance_insights,
    _generate_performance_insights,
    _display_cache_directory_info,
    _handle_cache_commands
)
from rich.table import Table


@patch('crackerjack.cli.cache_handlers.CrackerjackCache')
def test_handle_clear_cache_success(mock_cache_class):
    """Test handle_clear_cache function with successful cleanup."""
    mock_cache = Mock()
    mock_cache.cleanup_all.return_value = {"hook_cache": 5, "result_cache": 3}
    mock_cache_class.return_value = mock_cache

    # Capture print output by patching the console
    with patch('crackerjack.cli.cache_handlers.console') as mock_console:
        handle_clear_cache()

        # Check that the console print methods were called appropriately
        assert mock_console.print.call_count >= 2  # At least table and success message


@patch('crackerjack.cli.cache_handlers.CrackerjackCache')
def test_handle_clear_cache_error(mock_cache_class):
    """Test handle_clear_cache function when an error occurs."""
    mock_cache_class.side_effect = Exception("Cache error")

    with patch('crackerjack.cli.cache_handlers.console') as mock_console:
        handle_clear_cache()

        # Check that error message was printed
        mock_console.print.assert_called()


@patch('crackerjack.cli.cache_handlers.CrackerjackCache')
def test_handle_cache_stats_success(mock_cache_class):
    """Test handle_cache_stats function with successful retrieval."""
    mock_cache = Mock()
    mock_cache.get_cache_stats.return_value = {
        "hook_cache": {
            "hit_rate_percent": 85.0,
            "hits": 100,
            "misses": 15,
            "total_entries": 50,
            "total_size_mb": 10.5
        }
    }
    mock_cache.enable_disk_cache = True
    mock_cache.cache_dir = Mock()
    mock_cache.cache_dir.exists.return_value = True
    mock_cache_class.return_value = mock_cache

    with patch('crackerjack.cli.cache_handlers.console') as mock_console:
        handle_cache_stats()

        # Check that the console print methods were called
        assert mock_console.print.call_count >= 2


@patch('crackerjack.cli.cache_handlers.CrackerjackCache')
def test_handle_cache_stats_error(mock_cache_class):
    """Test handle_cache_stats function when an error occurs."""
    mock_cache_class.side_effect = Exception("Stats error")

    with patch('crackerjack.cli.cache_handlers.console') as mock_console:
        handle_cache_stats()

        # Check that error message was printed
        mock_console.print.assert_called()


def test_create_cache_stats_table():
    """Test creation of cache stats table."""
    table = _create_cache_stats_table()

    assert isinstance(table, Table)
    assert table.title == "Cache Statistics"
    assert len(table.columns) == 6  # Cache Layer, Hit Rate %, Hits, Misses, Entries, Size (MB)


def test_populate_cache_stats_table():
    """Test populating cache stats table."""
    table = _create_cache_stats_table()

    stats = {
        "hook_cache": {
            "hit_rate_percent": 85.0,
            "hits": 100,
            "misses": 15,
            "total_entries": 50,
            "total_size_mb": 10.5
        },
        "result_cache": {
            "hit_rate_percent": 75.0,
            "hits": 80,
            "misses": 20,
            "total_entries": 30,
            "total_size_mb": 5.2
        }
    }

    totals = _populate_cache_stats_table(table, stats)

    # Check that rows were added
    assert len(table.rows) == 2  # Two cache types

    # Check that totals were calculated correctly
    expected_totals = {
        "hits": 180,      # 100 + 80
        "misses": 35,     # 15 + 20
        "entries": 80,    # 50 + 30
        "size": 15.7      # 10.5 + 5.2
    }
    assert totals == expected_totals


def test_get_hit_rate_style():
    """Test hit rate style determination."""
    # High hit rate (>70) should return green
    assert _get_hit_rate_style(80.0) == "green"
    assert _get_hit_rate_style(75.0) == "green"

    # Medium hit rate (40-70) should return yellow
    assert _get_hit_rate_style(60.0) == "yellow"
    assert _get_hit_rate_style(50.0) == "yellow"
    assert _get_hit_rate_style(45.0) == "yellow"

    # Low hit rate (<40) should return red
    assert _get_hit_rate_style(30.0) == "red"
    assert _get_hit_rate_style(20.0) == "red"
    assert _get_hit_rate_style(0.0) == "red"


def test_add_cache_totals_row():
    """Test adding totals row to cache stats table."""
    table = _create_cache_stats_table()

    totals = {
        "hits": 180,
        "misses": 20,
        "entries": 80,
        "size": 15.7
    }

    _add_cache_totals_row(table, totals)

    # Check that the totals row was added
    assert len(table.rows) >= 1  # At least one row was added


def test_generate_performance_insights():
    """Test generating performance insights."""
    # High hit rate
    insights = _generate_performance_insights(85.0, 50.0)
    assert "Excellent cache performance!" in insights[0]

    # Good hit rate
    insights = _generate_performance_insights(65.0, 50.0)
    assert "Good cache performance" in insights[0]

    # Moderate hit rate
    insights = _generate_performance_insights(45.0, 50.0)
    assert "Moderate cache performance" in insights[0]

    # Poor hit rate
    insights = _generate_performance_insights(20.0, 50.0)
    assert "Poor cache performance" in insights[0]

    # Large cache size
    insights = _generate_performance_insights(85.0, 150.0)
    large_cache_found = any("Large cache size" in insight for insight in insights)
    assert large_cache_found


@patch('crackerjack.cli.cache_handlers.console')
def test_display_cache_directory_info(mock_console):
    """Test displaying cache directory info."""
    mock_cache = Mock()
    mock_cache.enable_disk_cache = True
    mock_cache.cache_dir = Mock()
    mock_cache.cache_dir.__str__.return_value = "/tmp/cache"
    mock_cache.cache_dir.exists.return_value = True

    # Mock rglob to return some files
    mock_cache.cache_dir.rglob.return_value = [Mock(), Mock()]

    _display_cache_directory_info(mock_cache)

    # Check that console.print was called
    mock_console.print.assert_called()


def test_handle_cache_commands():
    """Test the _handle_cache_commands function."""
    # Test clear_cache=True
    with patch('crackerjack.cli.cache_handlers.handle_clear_cache') as mock_clear:
        result = _handle_cache_commands(clear_cache=True, cache_stats=False)
        assert result is True
        mock_clear.assert_called_once()

    # Test cache_stats=True
    with patch('crackerjack.cli.cache_handlers.handle_cache_stats') as mock_stats:
        result = _handle_cache_commands(clear_cache=False, cache_stats=True)
        assert result is True
        mock_stats.assert_called_once()

    # Test both False
    result = _handle_cache_commands(clear_cache=False, cache_stats=False)
    assert result is False
