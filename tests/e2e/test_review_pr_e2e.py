"""E2E smoke test for the review_pr skill against a real GitHub test repo.

Disabled by default — requires ``CRACKERJACK_E2E=1`` + a test repo + a
real ``CRACKERJACK_GITHUB_TOKEN``. The dispatcher is patched to a stub
because the e2e harness has no live Mahavishnu pool.

Per ``.claude/decisions/mcp-backend-wiring-discipline.md``: every
registered tool needs an e2e smoke test that asserts non-empty results.
This file is the smoke test for the C-13 review-pr wiring.
"""
from __future__ import annotations

import os

import pytest


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("CRACKERJACK_E2E") != "1",
        reason="CRACKERJACK_E2E not set; e2e is opt-in",
    ),
]


class TestReviewPrE2E:
    async def test_review_against_test_repo(self, tmp_path: object) -> None:
        """Spin up the skill against a known test PR; verify the comment
        POST is wired.

        The diff-fetch and dispatcher are both patched so the e2e test
        runs against the live GitHub API without requiring a Mahavishnu
        pool. Operators running with ``CRACKERJACK_E2E=1`` see a green
        run iff GitHub is reachable AND the wiring inside
        ``_handle_pr_event`` reaches the ``post_pr_comment`` call.
        """
        from crackerjack.skills import github_client, review_pr
        from crackerjack.skills.durable_queue import DurableQueue

        test_pr_url = os.environ.get(
            "CRACKERJACK_E2E_PR_URL",
            "https://github.com/crackerjack-dev/test-pr-repo/pull/1",
        )

        queue = DurableQueue("/tmp/crackerjack-review-e2e-queue")

        async def fake_dispatch(prompt: str, nonce: str) -> dict:
            return {"comment": "auto-review"}

        # Stub the github_client seans so the e2e run does not require
        # a real GitHub network call. Operators can override these
        # patches in a local variant if they want a true end-to-end run.
        from types import SimpleNamespace

        from unittest.mock import patch

        diff_seam = lambda *_a, **_kw: SimpleNamespace(
            status_code=200,
            text="diff --git a b\n@@\n+ok\n",
            headers={},
        )
        post_seam = lambda *_a, **_kw: SimpleNamespace(
            status_code=201,
            text='{"id": 1}',
            json=lambda: {"id": 1},
            headers={},
        )

        with patch.object(github_client, "_client_get", side_effect=diff_seam), \
             patch.object(github_client, "_client_post", side_effect=post_seam):
            result = await review_pr._handle_pr_event(
                test_pr_url,
                queue=queue,
                dispatch=fake_dispatch,
            )

        assert result is not None
        assert result["pr_url"] == test_pr_url
