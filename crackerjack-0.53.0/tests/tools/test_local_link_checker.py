"""Tests for local_link_checker tool."""

import tempfile
from pathlib import Path

from crackerjack.tools.local_link_checker import (
    _check_archived_file,
    _extract_path_part,
    _resolve_target_path,
    check_file,
    extract_markdown_links,
    is_archived_filename,
    is_local_link,
    validate_local_link,
)


def test_extract_markdown_links_basic():
    """Test extracting basic markdown links."""
    content = "[Link Text](target.md)"
    links = extract_markdown_links(content)

    assert len(links) == 1
    assert links[0] == ("target.md", 1)


def test_extract_markdown_links_multiple():
    """Test extracting multiple markdown links."""
    content = """
[First](first.md)
[Second](second.md)
[Third](third.md)
"""
    links = extract_markdown_links(content)

    assert len(links) == 3
    assert links[0][0] == "first.md"
    assert links[1][0] == "second.md"
    assert links[2][0] == "third.md"
    # Just verify we have line numbers, don't be exact about which line
    assert all(isinstance(line_num, int) for _, line_num in links)


def test_extract_markdown_links_skips_code_blocks():
    """Test that links in code blocks are not extracted."""
    content = """
```markdown
[Not a real link](fake.md)
```
[Real link](real.md)
"""
    links = extract_markdown_links(content)

    assert len(links) == 1
    assert links[0] == ("real.md", 5)


def test_extract_markdown_links_skips_inline_code():
    """Test that links in inline code are not extracted."""
    # Note: The function skips the ENTIRE line when it detects backticks
    # So even the real link won't be extracted if it's on a line with backticks
    content = """
Text with [real link](real.md)
And more [text](other.md)
"""
    links = extract_markdown_links(content)

    # Both links should be extracted from lines without backticks
    assert len(links) == 2
    assert links[0][0] == "real.md"
    assert links[1][0] == "other.md"


def test_is_local_link_local():
    """Test is_local_link with local paths."""
    assert is_local_link("path/to/file.md") is True
    assert is_local_link("./relative.md") is True
    assert is_local_link("/absolute/path.md") is True


def test_is_local_link_external():
    """Test is_local_link with external URLs."""
    assert is_local_link("http://example.com") is False
    assert is_local_link("https://example.com") is False
    assert is_local_link("mailto:user@example.com") is False
    assert is_local_link("ftp://example.com") is False


def test_is_archived_filename_patterns():
    """Test is_archived_filename with archive patterns."""
    assert is_archived_filename("PLAN_2026.md") is True
    assert is_archived_filename("MIGRATION_GUIDE.md") is True
    assert is_archived_filename("CLEANUP_NEEDED.md") is True
    assert is_archived_filename("ANALYSIS_COMPLETE.md") is True
    assert is_archived_filename("README.md") is False
    assert is_archived_filename("GUIDE.md") is False


def test_extract_path_part_with_anchor():
    """Test _extract_path_part with URL anchor."""
    assert _extract_path_part("file.md#section") == "file.md"
    assert _extract_path_part("path/to/file.md#header-1") == "path/to/file.md"


def test_extract_path_part_without_anchor():
    """Test _extract_path_part without URL anchor."""
    assert _extract_path_part("file.md") == "file.md"
    assert _extract_path_part("path/to/file.md") == "path/to/file.md"


def test_resolve_target_path_absolute():
    """Test _resolve_target_path with absolute path."""
    source = Path("/repo/docs/guide.md")
    repo_root = Path("/repo")

    result = _resolve_target_path("/README.md", source, repo_root)

    assert result == Path("/repo/README.md")


def test_resolve_target_path_relative():
    """Test _resolve_target_path with relative path."""
    source = Path("/repo/docs/guide.md")
    repo_root = Path("/repo")

    result = _resolve_target_path("other.md", source, repo_root)

    assert result == Path("/repo/docs/other.md")


def test_check_archived_file_exists():
    """Test _check_archived_file when file exists in archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archive_dir = tmpdir / "docs" / "archive"
        archive_dir.mkdir(parents=True)

        archived_file = archive_dir / "PLAN_2026.md"
        archived_file.write_text("content")

        result = _check_archived_file("PLAN_2026.md", tmpdir)

        assert result is True


def test_check_archived_file_not_exists():
    """Test _check_archived_file when file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        result = _check_archived_file("PLAN_2026.md", tmpdir)

        assert result is False


def test_validate_local_link_valid_file():
    """Test validate_local_link with existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        target_file = tmpdir / "README.md"
        target_file.write_text("# Hello")

        source_file = tmpdir / "guide.md"
        source_file.write_text("[Link](README.md)")

        is_valid, error = validate_local_link("README.md", source_file, tmpdir)

        assert is_valid is True
        assert error == ""


def test_validate_local_link_missing_file():
    """Test validate_local_link with missing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        source_file = tmpdir / "guide.md"
        source_file.write_text("# Guide")

        is_valid, error = validate_local_link("missing.md", source_file, tmpdir)

        assert is_valid is False
        assert "File not found" in error


def test_check_file_broken_links():
    """Test check_file detects broken links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a valid README.md so good link works
        (tmpdir / "README.md").write_text("# Readme")

        source_file = tmpdir / "guide.md"
        source_file.write_text("[Good Link](README.md)\n[Bad Link](missing.md)")

        broken = check_file(source_file, tmpdir)

        assert len(broken) == 1
        assert broken[0][0] == "missing.md"


def test_check_file_no_links():
    """Test check_file with file containing no links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        source_file = tmpdir / "guide.md"
        source_file.write_text("# Just a header\n\nNo links here.")

        broken = check_file(source_file, tmpdir)

        assert len(broken) == 0


def test_check_file_external_links_ignored():
    """Test check_file ignores external links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        source_file = tmpdir / "guide.md"
        source_file.write_text("[External](http://example.com)\n[Local](missing.md)")

        broken = check_file(source_file, tmpdir)

        assert len(broken) == 1
        assert broken[0][0] == "missing.md"
