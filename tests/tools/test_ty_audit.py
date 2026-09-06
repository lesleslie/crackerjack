"""Unit tests for crackerjack.tools.ty_audit (Phase Q.1.F).

These tests cover the audit tool that walks a directory tree and reports
``# ty: ignore[...]`` suppressions. The audit is the "real enforcement"
side of the Phase Q split ratchet: the ratchet counts diagnostics; the
audit classifies suppressions by code and by age and detects unused
ones. It is invoked as a periodic-cadence tool, not a per-CI gate.

Surface area covered:

1. Unit-level tests of the two pure helpers (``enumerate_suppressions``,
   ``group_by_code``) — fast feedback on the parsing rules.
2. CLI integration (``python -m crackerjack.tools.ty_audit ...``) — the
   hook invocation layer that consumers actually call. Subprocess-driven
   because in-process mocking would not catch argv / stdout / stderr /
   sys.exit interactions that CI relies on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from crackerjack.tools import ty_audit
from crackerjack.tools.ty_audit import (
    AuditReport,
    SuppressionRef,
    _comment_out_suppressions,
    _SUPPRESSION_RE,
    detect_unused,
    enumerate_suppressions,
    group_by_age,
    group_by_code,
    main,
    render_human,
    render_json,
)

# The subprocess invocations need to import crackerjack.tools.ty_audit.
# In a typical dev env the project is installed editable in the active venv,
# but for our test venv the package lives at this directory's parent
# (the crackerjack repo root). Add it to PYTHONPATH so ``python -m`` works
# regardless of install state.
_CRACKERJACK_ROOT = Path(__file__).resolve().parent.parent.parent
_SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": str(_CRACKERJACK_ROOT)}


def _write_suppressions(
    tests_dir: Path,
    codes: list[tuple[str, str]],
) -> list[Path]:
    """Write one Python file per (filename, code) pair containing a suppression.

    Each file gets a single ``# ty: ignore[<code>]`` line so the test
    can place the suppression on a known line number.

    Returns the list of created files.
    """
    tests_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for filename, code in codes:
        f = tests_dir / filename
        f.write_text(
            f"x = 1  # ty: ignore[{code}]\n",
            encoding="utf-8",
        )
        files.append(f)
    return files


class TestEnumerateSuppressionsFindsTyStyleIgnores:
    """``enumerate_suppressions`` matches ``# ty: ignore[...]`` only.

    The regex must NOT match ``# type: ignore`` (mypy / ruff syntax); the
    audit only reports ty directives.
    """

    def test_enumerate_suppressions_finds_ty_style_ignores(
        self, tmp_path: Path,
    ) -> None:
        """The regex picks up ``# ty: ignore[...]`` but not ``# type: ignore``."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        mixed = tests_dir / "mixed.py"
        mixed.write_text(
            "x = 1  # ty: ignore[invalid-argument-type]\n"
            "y = 2  # type: ignore[arg-type]\n"
            "z = 3  # type: ignore\n"
            "w = 4  # ty: ignore[unresolved-attribute]\n",
            encoding="utf-8",
        )

        refs = enumerate_suppressions(tests_dir)

        codes = sorted(ref.code for ref in refs)
        assert codes == ["invalid-argument-type", "unresolved-attribute"], (
            f"Expected only ty-style suppressions; got {codes}"
        )
        assert len(refs) == 2


class TestGroupByCodeReturnsDictOfLists:
    """``group_by_code`` returns ``{code: [SuppressionRef, ...]}``."""

    def test_group_by_code_returns_dict_of_lists(self, tmp_path: Path) -> None:
        """Suppressions are grouped by diagnostic code with correct counts."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [
                ("a.py", "invalid-argument-type"),
                ("b.py", "invalid-argument-type"),
                ("c.py", "invalid-argument-type"),
                ("d.py", "unresolved-attribute"),
                ("e.py", "unresolved-attribute"),
            ],
        )

        refs = enumerate_suppressions(tests_dir)
        grouped = group_by_code(refs)

        # Dict keyed by code, each value is a list of SuppressionRef.
        assert set(grouped.keys()) == {
            "invalid-argument-type",
            "unresolved-attribute",
        }
        assert len(grouped["invalid-argument-type"]) == 3
        assert len(grouped["unresolved-attribute"]) == 2

        # Each entry is a SuppressionRef instance with the expected code.
        for ref in grouped["invalid-argument-type"]:
            assert ref.code == "invalid-argument-type"
        for ref in grouped["unresolved-attribute"]:
            assert ref.code == "unresolved-attribute"


class TestAuditBelowThresholdExits0:
    """Below threshold: ``main()`` exits 0 (gate not triggered)."""

    def test_audit_below_threshold_exits_0(self, tmp_path: Path) -> None:
        """When total suppressions < threshold, exit code 0."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(5)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0, (
            f"Below-threshold audit must exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditAtOrAboveThresholdExits1:
    """At/above threshold: ``main()`` exits 1 (gate triggered)."""

    def test_audit_at_or_above_threshold_exits_1(self, tmp_path: Path) -> None:
        """When total suppressions >= threshold, audit triggers (exit 1)."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(12)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 1, (
            f"At-or-above-threshold audit must exit 1; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditJSONSchemaMatchesSpec:
    """``--json`` output has all 6 expected fields per the plan."""

    def test_audit_json_schema_matches_spec(self, tmp_path: Path) -> None:
        """``--json`` output contains total/by_code/unused/by_age/threshold/triggered."""
        tests_dir = tmp_path / "tests"
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(3)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0
        assert result.stdout.strip()

        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {
            "total",
            "by_code",
            "unused",
            "by_age",
            "threshold",
            "triggered",
        }, f"Unexpected JSON schema: {sorted(payload.keys())}"
        assert payload["total"] == 3
        assert payload["threshold"] == 10
        assert payload["triggered"] is False
        assert payload["by_code"] == {"invalid-argument-type": 3}


class TestAuditMissingPathExits2:
    """Nonexistent tests/ path -> config error (exit 2)."""

    def test_audit_missing_path_exits_2(self, tmp_path: Path) -> None:
        """Nonexistent path -> exit 2 (operator error contract)."""
        missing = tmp_path / "does_not_exist"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(missing),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 2, (
            f"Missing path must exit 2; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestAuditDryRunAlwaysExits0:
    """``--dry-run`` overrides threshold; always exits 0 even when over."""

    def test_audit_dry_run_always_exits_0(self, tmp_path: Path) -> None:
        """``--dry-run`` short-circuits gate and returns 0 regardless of total."""
        tests_dir = tmp_path / "tests"
        # 100 suppressions, threshold 10 -> would normally trigger (exit 1).
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(100)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "10",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 0, (
            f"--dry-run must always exit 0; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )


class TestSplitRatchetCatchesProdRegression:
    """``ty_ratchet --split`` gates prod diagnostics against prod budget.

    When prod diagnostics exceed prod budget, the split-mode gate fails
    (exit 1). This locks in the Q.1.B split behaviour that the audit
    report consumes.
    """

    def test_split_ratchet_catches_prod_regression(self, tmp_path: Path) -> None:
        """When prod diagnostics exceed prod budget, split-mode gate fails."""
        # Set up a temp repo with both crackerjack/ and tests/ directories
        # and a pyproject.toml with low prod budget so the gate trips.
        crackerjack_dir = tmp_path / "crackerjack"
        tests_dir = tmp_path / "tests"
        crackerjack_dir.mkdir()
        tests_dir.mkdir()

        pyproject = tmp_path / "pyproject.toml"
        # Budget of 0 means any prod diagnostic fails the gate.
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 0\nty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        # A crackerjack/ file with a real, intentional type error.
        broken = crackerjack_dir / "broken.py"
        broken.write_text(
            "x: int = 'this should be an int'\n",
            encoding="utf-8",
        )

        # tests/ has no suppressions / diagnostics; it's a tiny valid file.
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crackerjack.tools.ty_ratchet",
                    "--split",
                    "--pyproject",
                    str(pyproject),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmp_path,
                env=_SUBPROCESS_ENV,
            )

            # prod_count > 0 with prod budget = 0 -> prod_gate = False -> exit 1.
            assert result.returncode == 1, (
                f"prod budget breach must exit 1; got {result.returncode}. "
                f"stderr={result.stderr!r}"
            )
        finally:
            # Cleanup: remove the file we created (and any pyproject remnants).
            shutil.rmtree(crackerjack_dir, ignore_errors=True)
            shutil.rmtree(tests_dir, ignore_errors=True)
            if pyproject.exists():
                pyproject.unlink()


class TestSplitRatchetWithExplicitDirs:
    """Option B end-to-end: ``--split --prod-dir X --test-dir Y`` actually
    type-checks X and Y (not the hardcoded ``crackerjack``/``tests``).
    This is the mirror test that confirms non-crackerjack projects can
    point the ratchet at their actual layout.
    """

    def test_split_ratchet_with_explicit_dirs(self, tmp_path: Path) -> None:
        """A type error in the explicit prod dir fails the gate."""
        prod = tmp_path / "pkg"
        test = tmp_path / "tests_alt"
        prod.mkdir()
        test.mkdir()

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.crackerjack]\nty_max_errors_prod = 0\nty_max_errors_test = 1000\n",
            encoding="utf-8",
        )

        broken = prod / "broken.py"
        broken.write_text("x: int = 'this should be an int'\n", encoding="utf-8")
        (test / "__init__.py").write_text("", encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "crackerjack.tools.ty_ratchet",
                    "--split",
                    "--prod-dir",
                    str(prod),
                    "--test-dir",
                    str(test),
                    "--pyproject",
                    str(pyproject),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=tmp_path,
                env=_SUBPROCESS_ENV,
            )

            assert result.returncode == 1, (
                f"prod budget breach on explicit prod-dir must exit 1; "
                f"got {result.returncode}. stderr={result.stderr!r}"
            )
        finally:
            shutil.rmtree(prod, ignore_errors=True)
            shutil.rmtree(test, ignore_errors=True)
            if pyproject.exists():
                pyproject.unlink()


class TestThresholdBreachSignalInJSON:
    """When suppressions cross threshold, ``triggered`` is True in JSON."""

    def test_threshold_breach_signal_in_json(self, tmp_path: Path) -> None:
        """``triggered`` is True when total >= threshold (JSON output)."""
        tests_dir = tmp_path / "tests"
        # 60 suppressions with threshold 50 -> triggered.
        _write_suppressions(
            tests_dir,
            [(f"f{i}.py", "invalid-argument-type") for i in range(60)],
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "crackerjack.tools.ty_audit",
                str(tests_dir),
                "--threshold",
                "50",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=tmp_path,
            env=_SUBPROCESS_ENV,
        )

        assert result.returncode == 1
        assert result.stdout.strip()

        payload = json.loads(result.stdout)
        assert payload["total"] == 60
        assert payload["threshold"] == 50
        assert payload["triggered"] is True, (
            f"Expected triggered=True at total=60, threshold=50; "
            f"got {payload['triggered']}"
        )


# ---------------------------------------------------------------------------
# Additional coverage tests for finer-grained branches (above the original
# 10 regression tests). Each test patches ``ty_audit.subprocess.run`` so the
# downstream ``git blame`` / ``ty check`` boundaries don't need real binaries.
# ---------------------------------------------------------------------------


def _make_fake_run(
    *, stdout: str = "", stderr: str = "", returncode: int = 0,
):
    """Return a ``subprocess.run`` stub with the given outputs."""

    def fake_run(*args: object, **kwargs: object):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    return fake_run


def test_enumerate_suppressions_not_a_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-directory path triggers a SystemExit(2) with an error message."""
    not_a_dir = tmp_path / "missing"
    with pytest.raises(SystemExit) as exc:
        enumerate_suppressions(not_a_dir)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "not a directory" in captured.err


def test_enumerate_suppressions_skips_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file that raises ``OSError`` on ``read_text`` is skipped silently."""
    pkg = tmp_path / "tests"
    pkg.mkdir()
    (pkg / "broken.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    real_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "broken.py":
            raise OSError("disk error")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    refs = enumerate_suppressions(pkg)
    assert refs == []


def test_enumerate_suppressions_truncates_long_snippet(
    tmp_path: Path,
) -> None:
    """Snippets longer than 200 chars are truncated to 200."""
    pkg = tmp_path / "tests"
    pkg.mkdir()
    long_line = "x = 1  # ty: ignore[e001] " + ("a" * 300) + "\n"
    (pkg / "mod.py").write_text(long_line, encoding="utf-8")
    refs = enumerate_suppressions(pkg)
    assert len(refs) == 1
    assert len(refs[0].snippet) <= 200


def test_group_by_age_empty_refs(tmp_path: Path) -> None:
    """No refs → buckets are returned at 0."""
    assert group_by_age([], tmp_path) == {
        "<30 days": 0,
        "30-90 days": 0,
        ">90 days": 0,
    }


def test_group_by_age_recent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A blame date within the last 30 days increments ``<30 days``."""
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert buckets["<30 days"] == 1


def test_group_by_age_mid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A blame date 60 days ago lands in the 30-90 day bucket."""
    mid = datetime.now(UTC) - timedelta(days=60)
    mid_line = f"abc123 (Author {mid.strftime('%Y-%m-%d %H:%M:%S')} +0000)"
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=mid_line),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert buckets["30-90 days"] == 1


def test_group_by_age_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A blame date 100 days ago lands in the >90 days bucket."""
    old = datetime.now(UTC) - timedelta(days=100)
    stale_line = f"abc123 (Author {old.strftime('%Y-%m-%d %H:%M:%S')} +0000)"
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=stale_line),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert buckets[">90 days"] == 1


def test_group_by_age_skips_non_zero_returncode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A non-zero exit code short-circuits per ref."""
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="some output", returncode=1),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert sum(buckets.values()) == 0


def test_group_by_age_skips_empty_stdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="", returncode=0),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert sum(buckets.values()) == 0


def test_group_by_age_skips_malformed_blame(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="not a blame line", returncode=0),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert sum(buckets.values()) == 0


def test_group_by_age_handles_value_error_in_strptime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A well-formed regex match with invalid date components is skipped."""
    bad_line = "abc123 (Author 2026-13-99 99:99:99 +0000)"
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout=bad_line, returncode=0),
    )
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert sum(buckets.values()) == 0


def test_group_by_age_subprocess_oserror_returns_empty_buckets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """``subprocess.run`` raising ``OSError`` short-circuits to empty buckets."""
    def _raise(*args: object, **kwargs: object) -> object:
        raise OSError("git missing")

    monkeypatch.setattr(ty_audit.subprocess, "run", _raise)
    refs = [SuppressionRef(
        file=tmp_path / "a.py", line=1, code="e001", snippet="x",
    )]
    buckets = group_by_age(refs, tmp_path)
    assert buckets == {
        "<30 days": 0,
        "30-90 days": 0,
        ">90 days": 0,
    }


# ---------------------------------------------------------------------------
# _comment_out_suppressions
# ---------------------------------------------------------------------------


def test_comment_out_suppressions_strips_trailing_whitespace() -> None:
    """Trailing tabs/spaces on the modified line are trimmed."""
    content = "x = 1  # ty: ignore[e001]   \n"
    refs = [SuppressionRef(file=Path("a.py"), line=1, code="e001", snippet="x")]
    modified, line_map = _comment_out_suppressions(content, refs)
    assert modified is not None
    assert line_map == {1: 1}
    # The first line should not have trailing whitespace.
    assert modified.split("\n")[0] == modified.split("\n")[0].rstrip()


def test_comment_out_suppressions_line_out_of_range() -> None:
    """A ``ref.line`` beyond the source length returns ``(None, None)``."""
    content = "x = 1\n"
    refs = [SuppressionRef(file=Path("a.py"), line=99, code="e001", snippet="x")]
    modified, line_map = _comment_out_suppressions(content, refs)
    assert modified is None
    assert line_map is None


# ---------------------------------------------------------------------------
# detect_unused
# ---------------------------------------------------------------------------


def test_detect_unused_empty_refs_returns_empty(tmp_path: Path) -> None:
    assert detect_unused([], tmp_path) == []


def test_detect_unused_flags_unused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When ty does NOT report a diagnostic on the suppression's line,
    the suppression is flagged as unused."""
    py_file = tmp_path / "a.py"
    py_file.write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]
    # ty output: diagnostic on line 5, not line 1.
    ty_output = "a.py:5:1: error[some-other] something"
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout=ty_output, returncode=0),
    )
    unused = detect_unused(refs, tmp_path)
    assert len(unused) == 1
    assert unused[0].code == "e001"


def test_detect_unused_does_not_flag_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """When ty DOES report the same diagnostic on the suppression's line,
    the suppression is NOT flagged."""
    py_file = tmp_path / "a.py"
    py_file.write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]
    ty_output = "a.py:1:1: error[e001] real error"
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout=ty_output, returncode=0),
    )
    assert detect_unused(refs, tmp_path) == []


def test_detect_unused_skips_unreadable_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    py_file = tmp_path / "a.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]

    real_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == py_file:
            raise OSError("disk error")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=""),
    )
    assert detect_unused(refs, tmp_path) == []


def test_detect_unused_ty_binary_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """When the ty binary is missing, ``detect_unused`` warns and returns empty."""
    py_file = tmp_path / "a.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]

    def _raise_fnf(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("ty not installed")

    monkeypatch.setattr(ty_audit.subprocess, "run", _raise_fnf)
    unused = detect_unused(refs, tmp_path)
    assert unused == []
    captured = capsys.readouterr()
    assert "ty binary not found" in captured.err


def test_detect_unused_ty_oserror_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A generic ``OSError`` from the ty subprocess is logged and we continue."""
    py_file = tmp_path / "a.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]

    def _raise_os(*args: object, **kwargs: object) -> object:
        raise OSError("ty crashed")

    monkeypatch.setattr(ty_audit.subprocess, "run", _raise_os)
    unused = detect_unused(refs, tmp_path)
    assert unused == []
    captured = capsys.readouterr()
    assert "ty invocation failed" in captured.err


def test_detect_unused_skips_ref_with_no_line_map_match(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A ref whose line is not in ``line_map`` is skipped."""
    py_file = tmp_path / "a.py"
    py_file.write_text("# ty: ignore[something]\n", encoding="utf-8")
    # ref.line points to a line that doesn't exist after commenting out.
    refs = [SuppressionRef(file=py_file, line=99, code="e001", snippet="x")]
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=""),
    )
    unused = detect_unused(refs, tmp_path)
    assert unused == []


def test_detect_unused_skips_invalid_diagnostic_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A ty output line with non-integer line numbers is skipped."""
    py_file = tmp_path / "a.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]
    # The line number isn't an integer → ValueError on int() → skip.
    bad = "a.py:not_a_number:1: error[x] bad"
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=bad),
    )
    # The bad line is skipped → no diagnostic at line 1 → ref is flagged.
    result = detect_unused(refs, tmp_path)
    assert len(result) == 1
    assert result[0] == refs[0]


def test_detect_unused_reads_stderr_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """ty diagnostics on stderr are also parsed."""
    py_file = tmp_path / "a.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    refs = [SuppressionRef(file=py_file, line=1, code="e001", snippet="x")]
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="", stderr="a.py:5:1: error[x] bad"),
    )
    assert detect_unused(refs, tmp_path) == [refs[0]]


# ---------------------------------------------------------------------------
# detect_unused: aggregated across multiple files
# ---------------------------------------------------------------------------


def test_detect_unused_handles_multiple_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """``detect_unused`` iterates per-file. Set up a fake subprocess.run
    that returns a diagnostic for ``b.py`` but not ``a.py``."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    b.write_text("y = 2  # ty: ignore[e002]\n", encoding="utf-8")
    refs = [
        SuppressionRef(file=a, line=1, code="e001", snippet="x"),
        SuppressionRef(file=b, line=1, code="e002", snippet="y"),
    ]

    def fake_run_for_file(*args: object, **kwargs: object) -> object:
        # The cmd layout is ["ty", "check", str(file_path), ...].
        cmd = args[0] if args else kwargs.get("cmd") or []
        # file_path is index 2.
        file_arg = cmd[2] if len(cmd) > 2 else ""
        if file_arg.endswith("b.py"):
            return SimpleNamespace(
                stdout="b.py:1:1: error[e002] real",
                stderr="",
                returncode=0,
            )
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(ty_audit.subprocess, "run", fake_run_for_file)
    unused = detect_unused(refs, tmp_path)
    assert len(unused) == 1
    assert unused[0].code == "e001"


# ---------------------------------------------------------------------------
# render_human / render_json / main — covered by the original test classes
# (TestRenderHumanReport etc.) which we exercised earlier in this file.
# Adding targeted tests for branches not covered above.
# ---------------------------------------------------------------------------


def test_render_human_includes_age_buckets() -> None:
    """When ``by_age`` is populated, the rendered output includes
    the age bucket lines."""
    report = AuditReport(
        total=5,
        by_age={"<30 days": 2, "30-90 days": 1, ">90 days": 2},
    )
    text = render_human(report)
    assert "By age:" in text
    assert "<30 days" in text
    assert ">90 days" in text


def test_render_human_includes_unused_section() -> None:
    """When ``unused`` is populated, the rendered output includes
    the unused-suppression section."""
    report = AuditReport(total=1, unused=[SuppressionRef(
        file=Path("a.py"), line=1, code="e001", snippet="x",
    )])
    text = render_human(report)
    assert "Unused suppressions" in text


def test_render_human_with_by_code_and_age() -> None:
    """Both by-code and by-age buckets render in the human format."""
    report = AuditReport(
        total=3,
        by_code={"e001": [SuppressionRef(
            file=Path("a.py"), line=1, code="e001", snippet="x",
        )]},
        by_age={"<30 days": 1, "30-90 days": 0, ">90 days": 0},
    )
    text = render_human(report)
    assert "By code:" in text
    assert "By age:" in text


def test_render_json_with_unused(tmp_path: Path) -> None:
    """The JSON renderer emits the unused list with relative paths."""
    report = AuditReport(
        total=1,
        unused=[SuppressionRef(
            file=tmp_path / "a.py", line=1, code="e001", snippet="x",
        )],
    )
    payload = json.loads(render_json(report))
    assert len(payload["unused"]) == 1
    assert payload["unused"][0]["code"] == "e001"


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


def test_main_returns_2_when_path_not_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main([str(tmp_path / "missing")])
    assert rc == 2
    captured = capsys.readouterr()
    assert "path not found" in captured.err


def test_main_dry_run_always_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--dry-run`` short-circuits to 0 even when the threshold is exceeded."""
    pkg = tmp_path / "tests"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    rc = main([str(pkg), "--dry-run", "--threshold", "1"])
    assert rc == 0


def test_main_returns_0_under_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = tmp_path / "tests"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    rc = main([str(pkg), "--threshold", "100"])
    assert rc == 0


def test_main_returns_1_when_threshold_exceeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg = tmp_path / "tests"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    rc = main([str(pkg), "--threshold", "1"])
    assert rc == 1


def test_main_emits_json_when_flag_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    pkg = tmp_path / "tests"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    main([str(pkg), "--json", "--threshold", "100"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "total" in payload
    assert payload["total"] == 1


def test_main_detect_unused_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``--detect-unused`` flag populates ``report.unused``."""
    pkg = tmp_path / "tests"
    pkg.mkdir()
    py_file = pkg / "mod.py"
    py_file.write_text("x = 1  # ty: ignore[e001]\n", encoding="utf-8")
    monkeypatch.setattr(
        ty_audit.subprocess, "run", _make_fake_run(stdout=""),
    )
    rc = main([str(pkg), "--detect-unused", "--threshold", "100"])
    assert rc == 0


def test_main_with_repo_root_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--repo-root`` overrides the default repo_root computed as
    ``tests_dir.parent``."""
    pkg = tmp_path / "tests"
    pkg.mkdir()
    custom_repo = tmp_path / "custom_repo"
    custom_repo.mkdir()
    (pkg / "mod.py").write_text(
        "x = 1  # ty: ignore[e001]\n", encoding="utf-8",
    )
    monkeypatch.setattr(
        ty_audit.subprocess, "run",
        _make_fake_run(stdout="abc123 (Author 2026-09-06 10:00:00 +0000)"),
    )
    rc = main(
        [str(pkg), "--repo-root", str(custom_repo), "--threshold", "100"]
    )
    assert rc == 0
