from __future__ import annotations

from crackerjack.agents.base import IssueType
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.core.phase_coordinator import PhaseCoordinator


def test_determine_issue_type_routes_ruff_complexity() -> None:
    coordinator = AutofixCoordinator()

    issue_type = coordinator._determine_issue_type(
        "ruff",
        {"code": "C901", "message": "Function is too complex"},
    )

    assert issue_type is IssueType.COMPLEXITY


def test_determine_issue_type_routes_docs_links() -> None:
    coordinator = AutofixCoordinator()

    issue_type = coordinator._determine_issue_type(
        "check-local-links",
        {"message": "Broken link: File not found: ../QUICKSTART.md"},
    )

    assert issue_type is IssueType.DOCUMENTATION


def test_determine_issue_type_routes_ruff_export_errors() -> None:
    coordinator = AutofixCoordinator()

    issue_type = coordinator._determine_issue_type(
        "ruff",
        {"code": "F822", "message": 'Undefined name "bar" in __all__'},
    )

    assert issue_type is IssueType.DEAD_CODE


def test_should_show_ai_fix_banner_requires_verbose_or_ai_debug() -> None:
    coordinator = PhaseCoordinator.__new__(PhaseCoordinator)

    class Options:
        verbose = False
        ai_debug = False

    assert coordinator._should_show_ai_fix_banner(Options()) is False

    class VerboseOptions:
        verbose = True
        ai_debug = False

    assert coordinator._should_show_ai_fix_banner(VerboseOptions()) is True

    class DebugOptions:
        verbose = False
        ai_debug = True

    assert coordinator._should_show_ai_fix_banner(DebugOptions()) is True
