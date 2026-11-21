"""Documents describing a REMOVED subsystem must be marked as records.

The AI-fix subsystem was deleted from production on 2026-11-13 by
``docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md`` (-73
files, -52,338 lines). Seven documents still describe it, and until
2026-11-21 they all carried ``status: active`` or ``status: draft`` --
so the plan index presented work against code that no longer exists as
if it were still to be done.

Two separate things had to be true, and only the second was obvious:

* the documents had to be marked, and
* the marking had to be accurate.

``ARCHIVABLE_STATUSES`` (``crackerjack/core/lifecycle.py``) is
``frozenset({"shipped"})``, and it looked like the gate that stopped
these documents from being archived. It was not. The archiver's
detector (``DocumentationCategorizer``) matches by FILENAME, and none
of these seven matches any of its patterns, so they were never
proposed in the first place. Widening the status set would have moved
nothing. The documents were invisible to the archiver for a different
reason entirely.

So they are marked here in place, as ``status: complete`` +
``role: historical`` -- the treatment this repository already gives
``docs/plans/2026-08-06-ai-fix-external-loop.md``, whose subject still
exists. Marking them in place also keeps them in version control:
``.gitignore`` carries ``**/.archive/``, so a document MOVED into the
archive leaves version control, and these are the record of what was
built and why.

This test pins that marking, and pins the fact it depends on: the
modules these documents name must still be gone. If one is restored,
the documents stop being records of a removed subsystem and this test
fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Documents that describe the AI-fix subsystem, and the modules each
#: one names. Every listed module was deleted on 2026-11-13.
AI_FIX_RECORDS: dict[str, tuple[str, ...]] = {
    "docs/plans/2026-06-02-ai-fix-display-loop-bugs.md": (
        "crackerjack/core/autofix_coordinator.py",
        "crackerjack/services/ai_fix_progress.py",
        "crackerjack/ui/ai_fix_dashboard.py",
    ),
    "docs/plans/2026-07-11-ai-fix-e501-post-processor.md": (
        "crackerjack/agents/base.py",
        "crackerjack/ai_fix/code_post_processor.py",
    ),
    "docs/plans/2026-07-11-ai-fix-no-op-circuit-breaker.md": (
        "crackerjack/core/autofix_coordinator.py",
    ),
    "docs/plans/2026-07-11-ai-fix-regen-timeout.md": (
        "crackerjack/core/autofix_coordinator.py",
    ),
    "docs/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md": (
        "crackerjack/agents/coordinator.py",
        "crackerjack/agents/issue_clusterer.py",
        "crackerjack/agents/parallel_dispatcher.py",
        "crackerjack/core/autofix_coordinator.py",
        "crackerjack/core/preflight.py",
        "crackerjack/integration/mahavishnu_pool_dispatcher.py",
        "crackerjack/ui/ai_fix_dashboard.py",
    ),
    "docs/specs/2026-07-11-ai-fix-no-op-circuit-breaker-design.md": (
        "crackerjack/ai_fix/tightened_dispatcher.py",
        "crackerjack/core/autofix_coordinator.py",
        "crackerjack/tools/ty_imports.py",
    ),
    "docs/specs/2026-07-11-ai-fix-regen-timeout-design.md": (
        "crackerjack/core/autofix_coordinator.py",
        "crackerjack/tools/ty_imports.py",
    ),
}

#: The plans that performed the removals. Their work is done and
#: verifiable -- the files are gone -- so they are closed, not active.
REMOVAL_PLANS: tuple[str, ...] = (
    "docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md",
    "docs/plans/2026-11-14-remove-dead-module-cluster.md",
)


def _frontmatter(rel: str) -> dict[str, Any]:
    """Parse the YAML frontmatter of a repository document."""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    loaded = yaml.safe_load(text[3:end].lstrip("\n"))
    return loaded if isinstance(loaded, dict) else {}


class TestTheAiFixDocumentsAreRecords:
    """The seven documents that describe a removed subsystem."""

    @pytest.mark.parametrize("rel", sorted(AI_FIX_RECORDS))
    def test_is_not_presented_as_current_work(self, rel: str) -> None:
        front = _frontmatter(rel)
        assert front.get("status") == "complete", (
            f"{rel} still has status {front.get('status')!r}; a document "
            "describing code that was deleted must not read as current work"
        )
        assert front.get("role") == "historical", (
            f"{rel} still has role {front.get('role')!r}; it records a "
            "subsystem that was removed, so it is historical"
        )

    @pytest.mark.parametrize("rel", sorted(AI_FIX_RECORDS))
    def test_names_modules_that_are_still_gone(self, rel: str) -> None:
        for module in AI_FIX_RECORDS[rel]:
            assert not (REPO_ROOT / module).exists(), (
                f"{module} exists again, so {rel} is no longer a record of "
                "a removed subsystem"
            )

    @pytest.mark.parametrize("rel", sorted(AI_FIX_RECORDS))
    def test_points_at_the_removal_that_superseded_it(self, rel: str) -> None:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert (
            "2026-11-13-remove-dead-ai-fix-module-cluster.md" in text
        ), f"{rel} does not say which removal ended its subject matter"

    def test_the_cluster_is_exactly_seven_documents(self) -> None:
        assert len(AI_FIX_RECORDS) == 7


class TestTheRemovalPlansAreClosed:
    """The plans that performed the removals."""

    @pytest.mark.parametrize("rel", REMOVAL_PLANS)
    def test_is_marked_shipped(self, rel: str) -> None:
        front = _frontmatter(rel)
        assert front.get("status") == "shipped", (
            f"{rel} still has status {front.get('status')!r}; the removal it "
            "describes was executed, so the plan is closed"
        )

    @pytest.mark.parametrize("rel", REMOVAL_PLANS)
    def test_still_exists_in_version_control(self, rel: str) -> None:
        """The removal plans are the pointer the seven records cite.

        They are marked, not moved: ``.gitignore`` carries
        ``**/.archive/``, so a document moved into the archive leaves
        version control, and the record would go with it.
        """
        assert (REPO_ROOT / rel).is_file()
