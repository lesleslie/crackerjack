"""Tests for ``crackerjack.tools.jsonc``.

The module strips comments from ``.json`` files so the ``format-json``
and ``check-json`` hooks can retry a file that failed to parse. It was
moved out of ``crackerjack/core/autofix_coordinator.py`` when the AI-fix
module cluster was deleted; these tests cover the behaviour as moved.
"""

from __future__ import annotations

import json
from pathlib import Path

from crackerjack.tools.jsonc import (
    strip_jsonc_comments,
    strip_jsonc_comments_from_failed_json_files,
)


class TestStripJsoncComments:
    """``strip_jsonc_comments`` returns (stripped_content, had_comments)."""

    def test_file_without_comments_is_unchanged(self, tmp_path: Path) -> None:
        target = tmp_path / "plain.json"
        target.write_text('{"a": 1}\n', encoding="utf-8")

        stripped, had_comments = strip_jsonc_comments(target)

        assert had_comments is False
        assert stripped == '{"a": 1}\n'

    def test_hash_comment_is_removed(self, tmp_path: Path) -> None:
        target = tmp_path / "commented.json"
        target.write_text('{"a": 1}  # trailing note\n', encoding="utf-8")

        stripped, had_comments = strip_jsonc_comments(target)

        assert had_comments is True
        assert stripped == '{"a": 1}\n'
        assert json.loads(stripped) == {"a": 1}

    def test_whole_line_comment_is_removed(self, tmp_path: Path) -> None:
        target = tmp_path / "commented.json"
        target.write_text('# header\n{"a": 1}\n', encoding="utf-8")

        stripped, had_comments = strip_jsonc_comments(target)

        assert had_comments is True
        assert stripped == "\n" + '{"a": 1}\n'

    def test_hash_inside_a_string_is_not_a_comment(self, tmp_path: Path) -> None:
        target = tmp_path / "hash_in_string.json"
        target.write_text('{"a": "value # not a comment"}\n', encoding="utf-8")

        stripped, had_comments = strip_jsonc_comments(target)

        assert had_comments is False
        assert json.loads(stripped) == {"a": "value # not a comment"}

    def test_escaped_quote_does_not_end_the_string(self, tmp_path: Path) -> None:
        target = tmp_path / "escaped.json"
        target.write_text('{"a": "say \\"hi\\" # still a string"}\n', encoding="utf-8")

        stripped, had_comments = strip_jsonc_comments(target)

        assert had_comments is False
        assert json.loads(stripped) == {"a": 'say "hi" # still a string'}

    def test_unreadable_file_returns_empty_and_no_comments(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist.json"

        stripped, had_comments = strip_jsonc_comments(missing)

        assert stripped == ""
        assert had_comments is False


class TestStripJsoncCommentsFromFailedJsonFiles:
    """The file-level driver: finds tracked .json files and rewrites them."""

    def test_no_json_files_is_success(self, tmp_path: Path) -> None:
        assert strip_jsonc_comments_from_failed_json_files(tmp_path) is True

    def test_commented_file_is_rewritten(self, tmp_path: Path) -> None:
        target = tmp_path / "commented.json"
        target.write_text('{"a": 1}  # note\n', encoding="utf-8")

        assert strip_jsonc_comments_from_failed_json_files(tmp_path) is True

        assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}

    def test_valid_file_is_left_alone(self, tmp_path: Path) -> None:
        target = tmp_path / "plain.json"
        original = '{"a": 1}\n'
        target.write_text(original, encoding="utf-8")

        assert strip_jsonc_comments_from_failed_json_files(tmp_path) is True

        assert target.read_text(encoding="utf-8") == original

    def test_file_that_cannot_be_parsed_after_stripping_reports_failure(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "broken.json"
        target.write_text('{"a":  # comment\n', encoding="utf-8")

        assert strip_jsonc_comments_from_failed_json_files(tmp_path) is False
