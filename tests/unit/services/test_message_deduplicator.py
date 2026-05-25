"""Unit tests for message deduplication."""

from __future__ import annotations

import builtins
from unittest.mock import Mock, patch

import crackerjack.services.message_deduplicator as message_deduplicator_module
from crackerjack.services.message_deduplicator import (
    MessageDeduplicator,
    get_deduplicator,
    reset_deduplicator,
)


def test_add_message_tracks_first_occurrence_and_duplicates() -> None:
    deduplicator = MessageDeduplicator()

    first_added = deduplicator.add_message("hello", level="warning", context={"job": 1})
    second_added = deduplicator.add_message("hello", level="warning", context={"job": 2})
    other_added = deduplicator.add_message("hello", level="info")

    assert first_added is True
    assert second_added is False
    assert other_added is True
    assert deduplicator.messages["warning:hello"] == 2
    assert deduplicator.messages["info:hello"] == 1
    assert deduplicator.first_occurrence["warning:hello"] == {
        "message": "hello",
        "level": "warning",
        "context": {"job": 1},
        "count": 1,
    }
    assert deduplicator.total_messages == 3
    assert deduplicator.unique_messages == 2
    assert deduplicator.duplicate_count == 1


def test_disabled_deduplicator_bypasses_tracking() -> None:
    deduplicator = MessageDeduplicator(enabled=False)

    assert deduplicator.add_message("hello") is True
    assert deduplicator.should_show("hello") is True
    assert deduplicator.get_duplicates() == []
    assert deduplicator.get_summary() == ""
    assert deduplicator.total_messages == 0
    assert deduplicator.unique_messages == 0
    assert deduplicator.duplicate_count == 0


def test_should_show_and_empty_duplicate_list() -> None:
    deduplicator = MessageDeduplicator()

    assert deduplicator.should_show("fresh message") is True
    deduplicator.add_message("fresh message")
    assert deduplicator.should_show("fresh message") is False
    assert deduplicator.get_duplicates() == []


def test_get_duplicates_and_summary_sorting_and_truncation() -> None:
    deduplicator = MessageDeduplicator()
    long_message = "x" * 70

    deduplicator.add_message(long_message, level="error")
    deduplicator.add_message(long_message, level="error")
    deduplicator.add_message("short", level="warning")
    deduplicator.add_message("short", level="warning")
    deduplicator.add_message("short", level="warning")

    duplicates = deduplicator.get_duplicates()
    assert {entry["message"] for entry in duplicates} == {long_message, "short"}

    summary = deduplicator.get_summary()
    assert summary.startswith("\n📊 Duplicate Message Summary:")
    assert ' [WARNING] "short" - appeared 3 times' in summary
    assert ' [ERROR] "' + ("x" * 60) + '..." - appeared 2 times' in summary


def test_print_summary_uses_panel_when_rich_is_available() -> None:
    deduplicator = MessageDeduplicator()
    deduplicator.add_message("repeat")
    deduplicator.add_message("repeat")
    console = Mock()

    deduplicator.print_summary(console)

    console.print.assert_called_once()
    panel = console.print.call_args.args[0]
    assert panel.renderable == deduplicator.get_summary()


def test_print_summary_falls_back_when_rich_panel_import_fails() -> None:
    deduplicator = MessageDeduplicator()
    deduplicator.add_message("repeat")
    deduplicator.add_message("repeat")
    console = Mock()
    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == "rich.panel":
            raise ImportError("missing panel")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        deduplicator.print_summary(console)

    console.print.assert_called_once_with(deduplicator.get_summary())


def test_print_summary_skips_empty_summary() -> None:
    deduplicator = MessageDeduplicator()
    console = Mock()

    deduplicator.print_summary(console)

    console.print.assert_not_called()


def test_reset_and_singleton_helpers() -> None:
    message_deduplicator_module._deduplicator = None

    first = get_deduplicator()
    assert isinstance(first, MessageDeduplicator)
    assert message_deduplicator_module._deduplicator is first

    first.add_message("hello")
    second = get_deduplicator()
    assert first is second

    reset_deduplicator()
    assert first.total_messages == 0
    assert first.unique_messages == 0

    third = get_deduplicator()
    assert third is first
    assert third.total_messages == 0


def test_reset_deduplicator_creates_instance_when_missing() -> None:
    message_deduplicator_module._deduplicator = None

    reset_deduplicator()

    assert isinstance(message_deduplicator_module._deduplicator, MessageDeduplicator)
