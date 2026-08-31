from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from crackerjack.services import frontmatter as validator_module


def _make_missing_frontmatter_file(tmp_path: Path) -> Path:
    md = tmp_path / "no_front.md"
    md.write_text("# Heading only\n\nNo frontmatter here.\n", encoding="utf-8")
    return md


def test_validate_file_accepts_valid_document(tmp_path: Path) -> None:
    """validate_file returns status='ok' for a well-formed document."""
    md = tmp_path / "ok.md"
    md.write_text(
        "---\n"
        "status: draft\n"
        "role: implementation\n"
        "date: 2026-01-01\n"
        "last_reviewed: 2026-01-01\n"
        "topic: example-topic\n"
        "---\n"
        "# Title\n\nbody\n",
        encoding="utf-8",
    )
    result = validator_module.validate_file(
        md,
        rel="ok.md",
        repo_root=tmp_path,
        known_files=set(),
        known_topics={"example-topic"},
        strict=False,
        allow_nonstandard=False,
        validate_links=False,
        skip_link_note=False,
    )
    assert result.status == "ok"
    assert result.errors == []


def test_extract_frontmatter_returns_mapping() -> None:
    """extract_frontmatter parses a YAML block into a dict."""
    text = (
        "---\n"
        "status: draft\n"
        "role: canonical\n"
        "---\n"
        "body\n"
    )
    front, err, _ = validator_module.extract_frontmatter(text)
    assert err is None
    assert isinstance(front, dict)
    assert front.get("status") == "draft"
    assert front.get("role") == "canonical"


def test_main_accepts_repo_root_flag(tmp_path: Path) -> None:
    """The validator's main() accepts --repo-root as a CLI argument."""
    plans = tmp_path / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "ok.md").write_text(
        "---\n"
        "status: draft\n"
        "role: implementation\n"
        "date: 2026-01-01\n"
        "last_reviewed: 2026-01-01\n"
        "topic: example-topic\n"
        "---\n"
        "# Hi\n",
        encoding="utf-8",
    )
    rc = validator_module.main(
        [
            "--repo-root",
            str(tmp_path),
            "--json",
            "--allow-nonstandard",
            "--store",
            "plans",
        ]
    )
    assert rc == 0


def test_validator_module_has_no_main_block() -> None:
    """The validator module is importable as a library; no __main__ block."""
    src = inspect.getsource(validator_module)
    assert '__name__ == "__main__"' not in src
    assert "if __name__ == '__main__'" not in src


def test_extract_frontmatter_returns_none_for_underscore_section_separator(
    tmp_path, monkeypatch
) -> None:
    """Files that use ______________________ section separators must NOT be parsed as frontmatter.

    Regression test for the 2026-07-27 dhara consumer migration ship-blocker:
    the previous regex accepted `___` as a frontmatter delimiter AND matched
    the body until the next such line, swallowing markdown and failing
    yaml.safe_load with frontmatter_parse.
    """
    from crackerjack.services.frontmatter import extract_frontmatter

    # Leading section-separator line followed by metadata row that is NOT valid YAML
    text = (
        "______________________________________________\n"
        "\n"
        "## status: complete role: historical date: 2026-07-17\n"
        "\n"
        "# The Real Title\n"
    )
    front, err, _ = extract_frontmatter(text)
    assert front is None, f"expected None (no match), got {front!r}"
    assert err is None, f"expected None error, got {err!r}"


def test_extract_frontmatter_underscore_line_in_middle_returns_none() -> None:
    """A `___` line in the middle of a file (mid-body) must not start a false match.

    Files like dhara's plan/spec use repeating `___` section separators
    throughout the body. The regex's opening match must require a *closing*
    `---` on its own line — never match `___`.
    """
    from crackerjack.services.frontmatter import extract_frontmatter

    text = (
        "______________________________________________\n"
        "\n"
        "## Section one content\n"
        "\n"
        "______________________________________________\n"
        "\n"
        "## Section two content\n"
    )
    front, err, _ = extract_frontmatter(text)
    assert front is None, f"expected None, got {front!r}"
    assert err is None, f"expected None error, got {err!r}"


def test_extract_frontmatter_still_parses_dash_delimited_block() -> None:
    """Sanity: tightening the regex must not break the `---` happy path."""
    import datetime as _dt

    from crackerjack.services.frontmatter import extract_frontmatter

    text = (
        "---\n"
        "status: complete\n"
        "role: historical\n"
        "date: 2026-07-17\n"
        "last_reviewed: 2026-07-17\n"
        "topic: persistence\n"
        "---\n"
        "\n"
        "# Title\n"
    )
    front, err, _ = extract_frontmatter(text)
    assert err is None, f"unexpected error {err!r}"
    assert front == {
        "status": "complete",
        "role": "historical",
        "date": _dt.date(2026, 7, 17),
        "last_reviewed": _dt.date(2026, 7, 17),
        "topic": "persistence",
    }, front
