"""Release audit check for mcp-common (and other Bodai components).

Verifies that:
1. CHANGELOG "Added" claims have corresponding source symbols
2. CHANGELOG "Removed" claims no longer have those source symbols
3. CLAUDE.md version claim matches pyproject.toml
4. CLAUDE.md coverage claim matches .coverage-ratchet.json
5. CLAUDE.md test count claim matches pytest --collect-only
6. CLAUDE.md package structure paths exist on disk

Used by `crackerjack --all` to prevent broken releases (e.g., 0.24.0
where documented methods were silently removed in the version bump).
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ClaimType(Enum):
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True)
class ChangelogClaim:
    claim_type: ClaimType
    symbol: str
    context: str = ""


@dataclass(frozen=True)
class ClaudeClaim:
    kind: str  # "version" | "coverage" | "test_count" | "package_path"
    value: str
    context: str = ""


@dataclass(frozen=True)
class VerifyResult:
    passed: bool
    source: str  # "changelog" | "claude_md"
    claim: ChangelogClaim | ClaudeClaim | None
    message: str


@dataclass
class ReleaseAuditReport:
    passed: bool
    results: list[VerifyResult] = field(default_factory=list)

    def format_text(self) -> str:
        lines = ["Release Audit Report", "===================="]
        for r in self.results:
            tag = "[PASS]" if r.passed else "[FAIL]"
            lines.append(f"{tag} {r.message}")
        n_fail = sum(1 for r in self.results if not r.passed)
        lines.append("")
        lines.append(f"Result: {'FAIL' if n_fail else 'PASS'} ({n_fail} errors)")
        return "\n".join(lines)

    def exit_code(self) -> int:
        return 0 if self.passed else 1


def _parse_changelog(text: str) -> list[ChangelogClaim]:
    """Parse CHANGELOG.md for Added/Removed claims.

    Recognizes both formats:
    - Structured: ### Added\n- `fully.qualified.symbol`
    - Prose: ### Added\n- Add SymbolName (Plan Task X)
    """
    claims: list[ChangelogClaim] = []
    current_section: ClaimType | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "### Added":
            current_section = ClaimType.ADDED
            continue
        if stripped == "### Removed":
            current_section = ClaimType.REMOVED
            continue
        if stripped.startswith("### "):
            current_section = None
            continue
        if current_section is None:
            continue
        if not stripped.startswith("- "):
            continue
        bullet = stripped[2:]
        # Try backticked fully-qualified first
        m = re.search(r"`([\w.]+)`", bullet)
        if m:
            symbol = m.group(1)
        else:
            # Try "Add/Remove Name" prose pattern
            m = re.match(r"(?:Add(?:ed|ing)?|Remov(?:ed|ing))\s+([\w.]+)", bullet)
            if not m:
                continue
            symbol = m.group(1)
        # Require module-qualified paths (contains at least one dot)
        # and validate the captured token is a valid Python identifier
        # path like "mymodule.MyClass.new_method" or
        # "mcp_common.cli.factory.MCPServerCLIFactory.register_lifecycle_handlers".
        # Bare words like "Prometheus" or "TLS" get rejected.
        if "." not in symbol or not re.fullmatch(
            r"[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)+", symbol
        ):
            continue
        claims.append(
            ChangelogClaim(
                claim_type=current_section,
                symbol=symbol,
                context=bullet,
            )
        )
    return claims


def _parse_claude_md(text: str) -> list[ClaudeClaim]:
    """Parse CLAUDE.md for version, coverage, test_count, package_path claims."""
    claims: list[ClaudeClaim] = []
    for line in text.splitlines():
        # Version: "Current Status: vX.Y.Z"
        m = re.search(r"Current Status:\s*v?(\d+\.\d+(?:\.\d+)?)", line)
        if m:
            claims.append(ClaudeClaim(kind="version", value=m.group(1), context=line.strip()))
            continue
        # Coverage: "X% line coverage" or "X% coverage"
        m = re.search(r"(\d+)\s*%\s*(?:line\s+)?coverage", line, re.IGNORECASE)
        if m:
            claims.append(ClaudeClaim(kind="coverage", value=m.group(1), context=line.strip()))
            continue
        # Test count: require canonical claim form "N tests total" (or
        # "N test total"). Reject incidental prose mentions like
        # "20 tests in module X" or table cells like "| 20 | ... |".
        m = re.search(r"(\d+)\s+tests?\s+total", line, re.IGNORECASE)
        if m:
            claims.append(ClaudeClaim(kind="test_count", value=m.group(1), context=line.strip()))
            continue
        # Package path: bullet under ## Package Structure
        m = re.match(r"\s*-\s+`?([\w/]+\.py)`?", line)
        if m:
            claims.append(ClaudeClaim(kind="package_path", value=m.group(1), context=line.strip()))
    return claims


def _symbol_in_source(symbol: str, source_root: Path) -> bool:
    """Grep source tree for a fully-qualified or short symbol definition."""
    parts = symbol.rsplit(".", 1)
    if len(parts) == 2:
        _module_path, name = parts
        # Try a few patterns: def name, class name, NAME =, etc.
        patterns = [
            rf"^\s*def\s+{re.escape(name)}\b",
            rf"^\s*class\s+{re.escape(name)}\b",
            rf"^\s*{re.escape(name)}\s*=",
        ]
        for py_file in source_root.rglob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
            except OSError:
                continue
            for pat in patterns:
                if re.search(pat, content, re.MULTILINE):
                    return True
        return False
    # Single-name symbol: same logic but no module qualifier
    return _symbol_in_source(f"{symbol}.{symbol.split('.')[-1]}", source_root)


def _verify_added(claim: ChangelogClaim, source_root: Path) -> VerifyResult:
    if _symbol_in_source(claim.symbol, source_root):
        return VerifyResult(True, "changelog", claim, f"CHANGELOG: {claim.symbol} added — verified")
    return VerifyResult(False, "changelog", claim, f"CHANGELOG claims {claim.symbol} was added but no definition found in source")


def _verify_removed(claim: ChangelogClaim, source_root: Path) -> VerifyResult:
    if not _symbol_in_source(claim.symbol, source_root):
        return VerifyResult(True, "changelog", claim, f"CHANGELOG: {claim.symbol} removed — verified")
    return VerifyResult(False, "changelog", claim, f"CHANGELOG claims {claim.symbol} was removed but definition still exists in source")


def _read_pyproject_version(path: Path) -> str | None:
    """Extract `version = "X.Y.Z"` from pyproject.toml."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _read_ratchet_floor(path: Path) -> float | None:
    """Extract `current_minimum` from .coverage-ratchet.json."""
    import json
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return float(data.get("current_minimum")) if "current_minimum" in data else None


def _count_tests(test_root: Path) -> int | None:
    """Run pytest --collect-only -q and parse the count."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-header"],
            cwd=test_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    output = result.stdout + result.stderr
    # Look for "N tests collected" or "N tests"
    m = re.search(r"(\d+)\s+tests?\s+(?:collected|found)", output)
    if m:
        return int(m.group(1))
    # Fallback: last numeric token in the summary line
    for line in reversed(output.splitlines()):
        m = re.match(r"=+\s*(\d+)\s+(?:passed|tests|collected)", line)
        if m:
            return int(m.group(1))
    return None


def _verify_version(claim: ClaudeClaim, pyproject_path: Path) -> VerifyResult:
    actual = _read_pyproject_version(pyproject_path)
    if actual is None:
        return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims version {claim.value} but pyproject.toml version could not be read")
    if claim.value == actual:
        return VerifyResult(True, "claude_md", claim, f"CLAUDE.md: version '{claim.value}' matches pyproject.toml")
    return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims version {claim.value} but pyproject.toml says {actual}")


def _verify_coverage(claim: ClaudeClaim, ratchet_path: Path) -> VerifyResult:
    actual = _read_ratchet_floor(ratchet_path)
    if actual is None:
        return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims {claim.value}% coverage but ratchet file could not be read")
    if float(claim.value) >= actual:
        return VerifyResult(True, "claude_md", claim, f"CLAUDE.md: coverage '{claim.value}%' meets ratchet baseline {actual}%")
    return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims {claim.value}% coverage but ratchet baseline is {actual}%")


def _verify_test_count(claim: ClaudeClaim, test_root: Path) -> VerifyResult:
    actual = _count_tests(test_root)
    if actual is None:
        return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims {claim.value} tests but pytest --collect-only could not be parsed")
    if int(claim.value) == actual:
        return VerifyResult(True, "claude_md", claim, f"CLAUDE.md: test count '{claim.value}' matches pytest")
    return VerifyResult(False, "claude_md", claim, f"CLAUDE.md claims {claim.value} tests but pytest reports {actual}")


def _verify_path(claim: ClaudeClaim, project_root: Path) -> VerifyResult:
    target = project_root / claim.value
    if target.exists():
        return VerifyResult(True, "claude_md", claim, f"CLAUDE.md: path '{claim.value}' exists")
    return VerifyResult(False, "claude_md", claim, f"CLAUDE.md references '{claim.value}' but no such file")


def check_release_audit(
    *,
    project_root: Path,
    changelog_path: Path,
    claude_md_path: Path,
    pyproject_path: Path,
    ratchet_path: Path,
    source_root: Path,
    test_root: Path,
) -> ReleaseAuditReport:
    report = ReleaseAuditReport(passed=True)

    try:
        changelog_text = changelog_path.read_text()
        claude_text = claude_md_path.read_text()
    except FileNotFoundError as e:
        report.results.append(VerifyResult(False, "changelog", None, f"Required file not found: {e.filename}"))
        report.passed = False
        return report

    # Verify CHANGELOG claims
    for claim in _parse_changelog(changelog_text):
        if claim.claim_type is ClaimType.ADDED:
            report.results.append(_verify_added(claim, source_root))
        else:
            report.results.append(_verify_removed(claim, source_root))

    # Verify CLAUDE.md claims
    for claim in _parse_claude_md(claude_text):
        if claim.kind == "version":
            report.results.append(_verify_version(claim, pyproject_path))
        elif claim.kind == "coverage":
            report.results.append(_verify_coverage(claim, ratchet_path))
        elif claim.kind == "test_count":
            report.results.append(_verify_test_count(claim, test_root))
        elif claim.kind == "package_path":
            report.results.append(_verify_path(claim, project_root))

    report.passed = all(r.passed for r in report.results)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Release audit check")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--changelog", type=Path, required=True)
    parser.add_argument("--claude-md", type=Path, required=True)
    parser.add_argument("--pyproject", type=Path, required=True)
    parser.add_argument("--ratchet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--test-root", type=Path, required=True)
    args = parser.parse_args()
    report = check_release_audit(
        project_root=args.project_root,
        changelog_path=args.changelog,
        claude_md_path=args.claude_md,
        pyproject_path=args.pyproject,
        ratchet_path=args.ratchet,
        source_root=args.source_root,
        test_root=args.test_root,
    )
    print(report.format_text())
    sys.exit(report.exit_code())
