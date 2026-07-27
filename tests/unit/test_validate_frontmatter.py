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
    front, err = validator_module.extract_frontmatter(text)
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
