"""Tests for ``crackerjack.checks.release_audit``.

The module-level audit function parses CHANGELOG.md + CLAUDE.md and
verifies each claim against project state. Tests build project trees
in ``tmp_path`` rather than depending on a sibling repo's fixtures.

Note: ``release_audit.py`` contains a pre-existing bug — lines 241 and
257 use ``except X, Y:`` (Python 2 syntax) which Python 3 parses as
``except X as Y:`` (a binding form). Those branches behave
differently from intended and tests verify observable behavior, not
the comment-claimed multi-except semantics.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.checks.release_audit import (
    ChangelogClaim,
    ClaimType,
    ClaudeClaim,
    ReleaseAuditReport,
    VerifyResult,
    _count_tests,
    _parse_changelog,
    _parse_claude_md,
    _read_pyproject_version,
    _read_ratchet_floor,
    _symbol_in_source,
    _verify_added,
    _verify_coverage,
    _verify_path,
    _verify_removed,
    _verify_test_count,
    _verify_version,
    check_release_audit,
)


# ---------------------------------------------------------------------------
# Dataclass / Enum surface
# ---------------------------------------------------------------------------


def test_claim_type_values() -> None:
    assert ClaimType.ADDED.value == "added"
    assert ClaimType.REMOVED.value == "removed"


def test_changelog_claim_defaults() -> None:
    c = ChangelogClaim(claim_type=ClaimType.ADDED, symbol="mymod.Foo")
    assert c.context == ""
    assert c.symbol == "mymod.Foo"


def test_claude_claim_required_fields() -> None:
    c = ClaudeClaim(kind="version", value="1.2.3")
    assert c.context == ""


def test_verify_result_constructable() -> None:
    r = VerifyResult(True, "changelog", None, "ok")
    assert r.passed is True
    assert r.source == "changelog"


def test_release_audit_report_defaults() -> None:
    rep = ReleaseAuditReport(passed=True)
    assert rep.results == []


def test_release_audit_report_format_text_no_results() -> None:
    rep = ReleaseAuditReport(passed=True)
    txt = rep.format_text()
    assert "Release Audit Report" in txt
    assert "Result: PASS" in txt
    assert "(0 errors)" in txt


def test_release_audit_report_format_text_with_failure() -> None:
    rep = ReleaseAuditReport(passed=False)
    rep.results.append(VerifyResult(False, "changelog", None, "boom"))
    txt = rep.format_text()
    assert "[FAIL] boom" in txt
    assert "Result: FAIL" in txt
    assert "(1 errors)" in txt


def test_release_audit_report_exit_code_pass() -> None:
    assert ReleaseAuditReport(passed=True).exit_code() == 0


def test_release_audit_report_exit_code_fail() -> None:
    assert ReleaseAuditReport(passed=False).exit_code() == 1


# ---------------------------------------------------------------------------
# _parse_changelog
# ---------------------------------------------------------------------------


def test_parse_changelog_added_backticked() -> None:
    text = "## v1.0.0\n### Added\n- `mymod.MyClass.new_method`\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].claim_type is ClaimType.ADDED
    assert out[0].symbol == "mymod.MyClass.new_method"


def test_parse_changelog_removed_backticked() -> None:
    text = "## v1.0.0\n### Removed\n- `mymod.OldClass.old_method`\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].claim_type is ClaimType.REMOVED


def test_parse_changelog_prose_add() -> None:
    """Prose pattern: 'Add MyClass.method' → 'MyClass.method'."""
    text = "## v1.0.0\n### Added\n- Add MyClass.method\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].symbol == "MyClass.method"


def test_parse_changelog_prose_add_repo_prefix() -> None:
    """Prose with repo prefix translates '-' → '_' and prepends."""
    text = "## v1.0.0\n### Added\n- mcp-common: Add MCPServerCLI.factory\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].symbol == "mcp_common.MCPServerCLI.factory"


def test_parse_changelog_prose_remove() -> None:
    text = "## v1.0.0\n### Removed\n- Removed OldClass.method\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].claim_type is ClaimType.REMOVED


def test_parse_changelog_prose_remove_ing_form() -> None:
    text = "## v1.0.0\n### Removed\n- Removing OldClass.method\n"
    out = _parse_changelog(text)
    assert len(out) == 1
    assert out[0].symbol == "OldClass.method"


def test_parse_changelog_section_change_resets() -> None:
    """A '### Other' header after Added/Removed resets current_section."""
    text = (
        "## v1.0.0\n"
        "### Added\n- `mymod.A`\n"
        "### Fixed\n- ignored\n"
        "### Removed\n- `mymod.B`\n"
    )
    out = _parse_changelog(text)
    assert [c.symbol for c in out] == ["mymod.A", "mymod.B"]
    assert out[0].claim_type is ClaimType.ADDED
    assert out[1].claim_type is ClaimType.REMOVED


def test_parse_changelog_bare_word_rejected() -> None:
    """Single-word bullets like 'Prometheus' lack a module path → skipped."""
    text = "## v1.0.0\n### Added\n- Prometheus\n"
    assert _parse_changelog(text) == []


def test_parse_changelog_bullet_without_dash_ignored() -> None:
    text = "## v1.0.0\n### Added\nthis is prose without dash\n"
    assert _parse_changelog(text) == []


def test_parse_changelog_no_added_section() -> None:
    text = "## v1.0.0\nSome prose with no Added/Removed sections.\n"
    assert _parse_changelog(text) == []


def test_parse_changelog_invalid_python_identifier_rejected() -> None:
    """The symbol must look like 'module.path.ClassName'."""
    text = "## v1.0.0\n### Added\n- `123abc.def`\n"
    assert _parse_changelog(text) == []


# ---------------------------------------------------------------------------
# _parse_claude_md
# ---------------------------------------------------------------------------


def test_parse_claude_md_version() -> None:
    text = "## Header\nCurrent Status: v1.2.3\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "version" and c.value == "1.2.3" for c in out)


def test_parse_claude_md_version_no_v_prefix() -> None:
    text = "Current Status: 1.2.3\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "version" and c.value == "1.2.3" for c in out)


def test_parse_claude_md_coverage() -> None:
    text = "92% line coverage\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "coverage" and c.value == "92" for c in out)


def test_parse_claude_md_coverage_no_line_word() -> None:
    text = "92% coverage\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "coverage" and c.value == "92" for c in out)


def test_parse_claude_md_test_count() -> None:
    text = "100 tests total\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "test_count" and c.value == "100" for c in out)


def test_parse_claude_md_test_count_singular() -> None:
    text = "1 test total\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "test_count" and c.value == "1" for c in out)


def test_parse_claude_md_test_count_rejects_prose_mention() -> None:
    """'20 tests in module X' is incidental prose — not 'total'."""
    text = "20 tests in module X\n"
    out = _parse_claude_md(text)
    assert not any(c.kind == "test_count" for c in out)


def test_parse_claude_md_package_path() -> None:
    text = "## Package Structure\n- `crackerjack/foo.py`\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "package_path" and c.value == "crackerjack/foo.py" for c in out)


def test_parse_claude_md_package_path_unquoted() -> None:
    text = "- crackerjack/foo.py\n"
    out = _parse_claude_md(text)
    assert any(c.kind == "package_path" and c.value == "crackerjack/foo.py" for c in out)


# ---------------------------------------------------------------------------
# _symbol_in_source
# ---------------------------------------------------------------------------


def test_symbol_in_source_def_function(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def my_func():\n    pass\n")
    assert _symbol_in_source("m.my_func", tmp_path) is True


def test_symbol_in_source_class(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("class MyClass:\n    pass\n")
    assert _symbol_in_source("m.MyClass", tmp_path) is True


def test_symbol_in_source_assignment(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("MY_CONSTANT = 42\n")
    assert _symbol_in_source("m.MY_CONSTANT", tmp_path) is True


def test_symbol_in_source_dataclass_field(tmp_path: Path) -> None:
    """Bug-fix regression: dataclass fields with annotations need [:=] pattern."""
    (tmp_path / "m.py").write_text(
        "from dataclasses import dataclass, field\n"
        "@dataclass\n"
        "class Settings:\n"
        "    eventbridge: 'EventBridgeSettings' = field(default_factory=dict)\n"
    )
    assert _symbol_in_source("Settings.eventbridge", tmp_path) is True


def test_symbol_in_source_missing_returns_false(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("x = 1\n")
    assert _symbol_in_source("m.nonexistent", tmp_path) is False


def test_symbol_in_source_recurses_subdirs(tmp_path: Path) -> None:
    sub = tmp_path / "pkg" / "deep"
    sub.mkdir(parents=True)
    (sub / "m.py").write_text("class Deep:\n    pass\n")
    assert _symbol_in_source("m.Deep", tmp_path) is True


def test_symbol_in_source_handles_oserror_on_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError on read_text is swallowed (continue), then matching files still get found."""
    (tmp_path / "good.py").write_text("class Foo:\n    pass\n")
    (tmp_path / "bad.py").write_text("class Bar:\n    pass\n")

    real_read_text = Path.read_text

    def fake_read_text(self: Path, *a: object, **kw: object) -> str:
        if self.name == "bad.py":
            raise OSError("simulated")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    # Symbol lives in good.py → must still be found despite bad.py raising.
    assert _symbol_in_source("good.Foo", tmp_path) is True
    # bad.py contains 'Bar' but is unreadable → not found.
    assert _symbol_in_source("bad.Bar", tmp_path) is False


def test_symbol_in_source_single_name(tmp_path: Path) -> None:
    """Single-name symbol (no dot) recurses with module=sym, name=sym."""
    (tmp_path / "thing.py").write_text("class thing:\n    pass\n")
    assert _symbol_in_source("thing", tmp_path) is True


def test_symbol_in_source_unreadable_dir_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If every file in the tree raises OSError on read, no symbol is found."""
    (tmp_path / "a.py").write_text("class A:\n    pass\n")

    def always_raise(self: Path, *a: object, **kw: object) -> str:
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "read_text", always_raise)
    assert _symbol_in_source("a.A", tmp_path) is False


# ---------------------------------------------------------------------------
# _verify_added / _verify_removed
# ---------------------------------------------------------------------------


def test_verify_added_found(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def hello():\n    pass\n")
    claim = ChangelogClaim(ClaimType.ADDED, "m.hello")
    r = _verify_added(claim, tmp_path)
    assert r.passed is True
    assert "added" in r.message


def test_verify_added_missing(tmp_path: Path) -> None:
    claim = ChangelogClaim(ClaimType.ADDED, "m.NotThere")
    r = _verify_added(claim, tmp_path)
    assert r.passed is False
    assert "no definition found" in r.message


def test_verify_removed_actually_removed(tmp_path: Path) -> None:
    """Removed claim + symbol gone from source → pass."""
    claim = ChangelogClaim(ClaimType.REMOVED, "m.NotThere")
    r = _verify_removed(claim, tmp_path)
    assert r.passed is True


def test_verify_removed_still_present(tmp_path: Path) -> None:
    """Removed claim + symbol still exists → fail."""
    (tmp_path / "m.py").write_text("def still_here():\n    pass\n")
    claim = ChangelogClaim(ClaimType.REMOVED, "m.still_here")
    r = _verify_removed(claim, tmp_path)
    assert r.passed is False
    assert "still exists" in r.message


# ---------------------------------------------------------------------------
# _read_pyproject_version
# ---------------------------------------------------------------------------


def test_read_pyproject_version_double_quoted(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\nversion = "1.2.3"\n')
    assert _read_pyproject_version(p) == "1.2.3"


def test_read_pyproject_version_single_quoted(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text("version = '4.5.6'\n")
    assert _read_pyproject_version(p) == "4.5.6"


def test_read_pyproject_version_missing_returns_none(tmp_path: Path) -> None:
    assert _read_pyproject_version(tmp_path / "missing.toml") is None


def test_read_pyproject_version_no_version_key(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\n')
    assert _read_pyproject_version(p) is None


# ---------------------------------------------------------------------------
# _read_ratchet_floor
# ---------------------------------------------------------------------------


def test_read_ratchet_floor_valid(tmp_path: Path) -> None:
    p = tmp_path / "ratchet.json"
    p.write_text(json.dumps({"current_minimum": 89.5}))
    assert _read_ratchet_floor(p) == 89.5


def test_read_ratchet_floor_missing_returns_none(tmp_path: Path) -> None:
    """File not found → None (does not raise)."""
    assert _read_ratchet_floor(tmp_path / "missing.json") is None


def test_read_ratchet_floor_no_current_minimum_key(tmp_path: Path) -> None:
    """No 'current_minimum' key → None (does not raise)."""
    p = tmp_path / "ratchet.json"
    p.write_text(json.dumps({"other": 1.0}))
    assert _read_ratchet_floor(p) is None


# ---------------------------------------------------------------------------
# _verify_version
# ---------------------------------------------------------------------------


def test_verify_version_matches(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('version = "1.2.3"\n')
    claim = ClaudeClaim(kind="version", value="1.2.3")
    r = _verify_version(claim, tmp_path / "pyproject.toml")
    assert r.passed is True


def test_verify_version_mismatch(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('version = "9.9.9"\n')
    claim = ClaudeClaim(kind="version", value="1.2.3")
    r = _verify_version(claim, tmp_path / "pyproject.toml")
    assert r.passed is False
    assert "9.9.9" in r.message


def test_verify_version_unreadable(tmp_path: Path) -> None:
    claim = ClaudeClaim(kind="version", value="1.2.3")
    r = _verify_version(claim, tmp_path / "missing.toml")
    assert r.passed is False
    assert "could not be read" in r.message


# ---------------------------------------------------------------------------
# _verify_coverage
# ---------------------------------------------------------------------------


def test_verify_coverage_meets_baseline(tmp_path: Path) -> None:
    (tmp_path / "ratchet.json").write_text(json.dumps({"current_minimum": 89.0}))
    claim = ClaudeClaim(kind="coverage", value="92")
    r = _verify_coverage(claim, tmp_path / "ratchet.json")
    assert r.passed is True


def test_verify_coverage_equals_baseline(tmp_path: Path) -> None:
    (tmp_path / "ratchet.json").write_text(json.dumps({"current_minimum": 92.0}))
    claim = ClaudeClaim(kind="coverage", value="92")
    r = _verify_coverage(claim, tmp_path / "ratchet.json")
    assert r.passed is True


def test_verify_coverage_below_baseline(tmp_path: Path) -> None:
    (tmp_path / "ratchet.json").write_text(json.dumps({"current_minimum": 95.0}))
    claim = ClaudeClaim(kind="coverage", value="80")
    r = _verify_coverage(claim, tmp_path / "ratchet.json")
    assert r.passed is False
    assert "below" in r.message or "ratchet baseline" in r.message


def test_verify_coverage_unreadable(tmp_path: Path) -> None:
    claim = ClaudeClaim(kind="coverage", value="92")
    r = _verify_coverage(claim, tmp_path / "missing.json")
    assert r.passed is False
    assert "could not be read" in r.message


# ---------------------------------------------------------------------------
# _verify_path
# ---------------------------------------------------------------------------


def test_verify_path_exists(tmp_path: Path) -> None:
    (tmp_path / "exists.py").touch()
    claim = ClaudeClaim(kind="package_path", value="exists.py")
    r = _verify_path(claim, tmp_path)
    assert r.passed is True


def test_verify_path_missing(tmp_path: Path) -> None:
    claim = ClaudeClaim(kind="package_path", value="does_not_exist.py")
    r = _verify_path(claim, tmp_path)
    assert r.passed is False
    assert "no such file" in r.message


# ---------------------------------------------------------------------------
# _count_tests (subprocess boundary)
# ---------------------------------------------------------------------------


def test_count_tests_parses_n_tests_collected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parses 'N tests collected' from pytest --collect-only output."""

    class _FakeCompleted:
        stdout = "5 tests collected\n"
        stderr = ""
        returncode = 0

    def fake_run(*a: object, **kw: object) -> _FakeCompleted:
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) == 5


def test_count_tests_parses_summary_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falls back to '=' summary line at end of output."""

    class _FakeCompleted:
        stdout = "===== 42 passed in 1.0s =====\n"
        stderr = ""
        returncode = 0

    def fake_run(*a: object, **kw: object) -> _FakeCompleted:
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) == 42


def test_count_tests_parses_n_tests_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'N tests found' is also accepted."""

    class _FakeCompleted:
        stdout = "10 tests found\n"
        stderr = ""
        returncode = 0

    def fake_run(*a: object, **kw: object) -> _FakeCompleted:
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) == 10


def test_count_tests_no_match_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCompleted:
        stdout = "no number here\n"
        stderr = ""
        returncode = 0

    def fake_run(*a: object, **kw: object) -> _FakeCompleted:
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) is None


def test_count_tests_subprocess_error_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*a: object, **kw: object) -> object:
        raise subprocess.SubprocessError("pytest crashed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) is None


def test_count_tests_filenotfound_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*a: object, **kw: object) -> object:
        raise FileNotFoundError("python not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _count_tests(tmp_path) is None


# ---------------------------------------------------------------------------
# _verify_test_count
# ---------------------------------------------------------------------------


def test_verify_test_count_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCompleted:
        stdout = "100 tests collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompleted()
    )
    claim = ClaudeClaim(kind="test_count", value="100")
    r = _verify_test_count(claim, tmp_path)
    assert r.passed is True


def test_verify_test_count_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCompleted:
        stdout = "42 tests collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompleted()
    )
    claim = ClaudeClaim(kind="test_count", value="100")
    r = _verify_test_count(claim, tmp_path)
    assert r.passed is False
    assert "42" in r.message


def test_verify_test_count_unparseable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCompleted:
        stdout = "no tests here\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompleted()
    )
    claim = ClaudeClaim(kind="test_count", value="100")
    r = _verify_test_count(claim, tmp_path)
    assert r.passed is False
    assert "could not be parsed" in r.message


# ---------------------------------------------------------------------------
# check_release_audit — full integration
# ---------------------------------------------------------------------------


def _make_minimal_project(tmp_path: Path) -> dict[str, Path]:
    """Build a project tree that passes all audits.

    The source file lives directly under ``tmp_path`` (not a subdir) so
    that ``project_root / "mymod.py"`` resolves correctly for the
    ``package_path`` claim verification.
    """
    (tmp_path / "mymod.py").write_text("class MyClass:\n    def new_method(self):\n        pass\n")
    src = tmp_path

    (tmp_path / "CHANGELOG.md").write_text(
        "## v1.0.0\n### Added\n- `mymod.MyClass.new_method`\n"
    )
    (tmp_path / "CLAUDE.md").write_text(
        "## Header\n"
        "Current Status: v1.0.0\n"
        "95% line coverage\n"
        "1 test total\n"
        "## Package Structure\n- `mymod.py`\n"
    )
    (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n')
    ratchet = tmp_path / "ratchet.json"
    ratchet.write_text(json.dumps({"current_minimum": 90.0}))
    return {
        "project_root": tmp_path,
        "changelog": tmp_path / "CHANGELOG.md",
        "claude_md": tmp_path / "CLAUDE.md",
        "pyproject": tmp_path / "pyproject.toml",
        "ratchet": ratchet,
        "source_root": src,
        "test_root": tmp_path,
    }


def test_check_release_audit_all_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid project → all claims pass → report.passed is True."""

    class _FakeCompleted:
        stdout = "1 test collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _FakeCompleted()
    )

    paths = _make_minimal_project(tmp_path)
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is True
    assert all(r.passed for r in report.results)


def test_check_release_audit_missing_changelog(tmp_path: Path) -> None:
    """If required file is missing, report fails immediately."""
    paths = _make_minimal_project(tmp_path)
    paths["changelog"].unlink()
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("not found" in r.message for r in report.results)


def test_check_release_audit_missing_claude_md(tmp_path: Path) -> None:
    paths = _make_minimal_project(tmp_path)
    paths["claude_md"].unlink()
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False


def test_check_release_audit_added_symbol_missing(tmp_path: Path) -> None:
    """Added claim with no matching symbol in source → fail."""
    paths = _make_minimal_project(tmp_path)
    paths["changelog"].write_text(
        "## v1.0.0\n### Added\n- `mymod.NotThere.new_method`\n"
    )
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("mymod.NotThere" in r.message for r in report.results)


def test_check_release_audit_removed_symbol_still_present(tmp_path: Path) -> None:
    """Removed claim but symbol still in source → fail."""
    paths = _make_minimal_project(tmp_path)
    paths["changelog"].write_text(
        "## v1.0.0\n### Removed\n- `mymod.MyClass.new_method`\n"
    )
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("still exists" in r.message for r in report.results)


def test_check_release_audit_version_mismatch(tmp_path: Path) -> None:
    paths = _make_minimal_project(tmp_path)
    paths["claude_md"].write_text(
        "Current Status: v9.9.9\n95% line coverage\n5 tests total\n## Package Structure\n- `mymod.py`\n"
    )
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("version" in r.message and "9.9.9" in r.message for r in report.results)


def test_check_release_audit_coverage_below_baseline(tmp_path: Path) -> None:
    paths = _make_minimal_project(tmp_path)
    paths["claude_md"].write_text(
        "Current Status: v1.0.0\n50% line coverage\n5 tests total\n## Package Structure\n- `mymod.py`\n"
    )
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("coverage" in r.message.lower() for r in report.results)


def test_check_release_audit_test_count_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _make_minimal_project(tmp_path)

    class _FakeCompleted:
        stdout = "100 tests collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())

    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("100" in r.message and "tests" in r.message for r in report.results)


def test_check_release_audit_path_missing(tmp_path: Path) -> None:
    paths = _make_minimal_project(tmp_path)
    paths["claude_md"].write_text(
        "Current Status: v1.0.0\n95% line coverage\n5 tests total\n"
        "## Package Structure\n- `does_not_exist.py`\n"
    )
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is False
    assert any("does_not_exist" in r.message for r in report.results)


def test_check_release_audit_no_ratchet_skips_coverage_check(tmp_path: Path) -> None:
    """When ratchet_path is None or missing, coverage claim is skipped."""
    paths = _make_minimal_project(tmp_path)
    paths["ratchet"].unlink()
    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=None,
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    # Coverage claim should be skipped (pass with 'skipped' message).
    skipped = [
        r for r in report.results
        if r.source == "claude_md" and r.claim and r.claim.kind == "coverage"
    ]
    assert skipped
    assert all(r.passed for r in skipped)
    assert any("skipped" in r.message for r in skipped)


def test_check_release_audit_empty_inputs_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty CHANGELOG + CLAUDE.md → no claims → passes."""
    paths = _make_minimal_project(tmp_path)
    paths["changelog"].write_text("")
    paths["claude_md"].write_text("")

    class _FakeCompleted:
        stdout = "0 tests collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())

    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is True


def test_check_release_audit_malformed_changelog_no_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CHANGELOG without '### Added'/'### Removed' headers → no claims."""
    paths = _make_minimal_project(tmp_path)
    paths["changelog"].write_text("## v1.0.0\nNo structured sections.\n")

    class _FakeCompleted:
        stdout = "1 test collected\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _FakeCompleted())

    report = check_release_audit(
        project_root=paths["project_root"],
        changelog_path=paths["changelog"],
        claude_md_path=paths["claude_md"],
        pyproject_path=paths["pyproject"],
        ratchet_path=paths["ratchet"],
        source_root=paths["source_root"],
        test_root=paths["test_root"],
    )
    assert report.passed is True


# ---------------------------------------------------------------------------
# __main__ CLI block (lines 427-448)
# ---------------------------------------------------------------------------


def test_main_block_pass_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running the module as a script with a valid project exits 0.

    ``--test-root`` points at an isolated dir containing one trivial test
    file, so the real ``pytest --collect-only`` subprocess returns a
    deterministic count.
    """
    paths = _make_minimal_project(tmp_path)

    # Isolate test_root so pytest --collect-only only sees our trivial test.
    isolated_tests = tmp_path / "isolated_tests"
    isolated_tests.mkdir()
    (isolated_tests / "conftest.py").write_text("")
    (isolated_tests / "test_one.py").write_text(
        "def test_x():\n    pass\n"
    )

    import sys as _sys
    rc = subprocess.call(
        [
            _sys.executable, "-m", "crackerjack.checks.release_audit",
            "--project-root", str(paths["project_root"]),
            "--changelog", str(paths["changelog"]),
            "--claude-md", str(paths["claude_md"]),
            "--pyproject", str(paths["pyproject"]),
            "--ratchet", str(paths["ratchet"]),
            "--source-root", str(paths["source_root"]),
            "--test-root", str(isolated_tests),
        ],
        cwd=str(tmp_path),
    )
    assert rc == 0


def test_main_block_fail_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running the module as a script with a broken project exits 1."""
    paths = _make_minimal_project(tmp_path)
    paths["claude_md"].write_text(
        "Current Status: v9.9.9\n95% line coverage\n5 tests total\n"
        "## Package Structure\n- `does_not_exist.py`\n"
    )

    isolated_tests = tmp_path / "isolated_tests"
    isolated_tests.mkdir()
    (isolated_tests / "conftest.py").write_text("")
    (isolated_tests / "test_one.py").write_text(
        "def test_x():\n    pass\n"
    )

    import sys as _sys
    rc = subprocess.call(
        [
            _sys.executable, "-m", "crackerjack.checks.release_audit",
            "--project-root", str(paths["project_root"]),
            "--changelog", str(paths["changelog"]),
            "--claude-md", str(paths["claude_md"]),
            "--pyproject", str(paths["pyproject"]),
            "--ratchet", str(paths["ratchet"]),
            "--source-root", str(paths["source_root"]),
            "--test-root", str(isolated_tests),
        ],
        cwd=str(tmp_path),
    )
    assert rc == 1
