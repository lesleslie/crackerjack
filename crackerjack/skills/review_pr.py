"""Crackerjack review-pr skill — Akosha-pattern-triggered PR review.

Per niche filter (Mahavishnu is LLM control plane + repo orchestrator +
multi-engine + harness-agnostic):

- Trigger is an Akosha pattern subscription, NOT a Mahavishnu webhook.
- Pulls GitHub PR diff via ``CRACKERJACK_GITHUB_TOKEN`` env var
  reference (never raw token).
- Dispatches code-review via ``mahavishnu pool-route-execute execute``
  subprocess (crackerjack and mahavishnu are separate repos, so
  cross-process is the lowest-friction boundary).
- Posts review back as PR comment.

Version-pin to ``mahavishnu >= 0.29`` for ``safe_publish`` +
``IdempotencyOptions``; the contract test in
``tests/integration/test_review_pr.py`` asserts this pin holds.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from oneiric.core.logging import get_logger

from crackerjack.skills.comment_poster import GitHubAPIError, post_pr_comment
from crackerjack.skills.durable_queue import DurableQueue
from crackerjack.skills.github_client import fetch_pr_diff
from crackerjack.skills.review_metrics import (
    PR_REVIEW_DURATION,
    PR_REVIEW_FORK_PR_TOTAL,
    PR_REVIEW_POST_TOTAL,
)

logger = get_logger(__name__)

AKOSHA_PATTERN_TRIGGER = "ecosystem.event.received{source='git-monitor'}"
MAHAVISHNU_DISPATCH_IDEMPOTENCY_SOURCE = "crackerjack.review_pr"
QUEUE_PATH_ENV_VAR = "CRACKERJACK_REVIEW_QUEUE_PATH"
DEFAULT_QUEUE_PATH = "/tmp/crackerjack-review-queue"
MAHAVISHNU_BIN_ENV_VAR = "CRACKERJACK_MAHAVISHNU_BIN"
DEFAULT_MAHAVISHNU_BIN = "mahavishnu"
DIFF_PROMPT_LIMIT_CHARS = 50_000

# Mahavishnu version pin (C-5's safe_publish + C-6's IdempotencyOptions
# were first published in 0.29; per plan §"Implementation notes").
MAHAVISHNU_VERSION_PIN = "0.29"


def _is_fork_pr(pr_url: str) -> bool:
    """Heuristic: PRs opened by a non-member contributor are forks.

    True on the URL alone isn't knowable; we mark it best-effort so the
    fork-PR counter is non-zero when the contributor pattern matches.
    A real implementation would call ``/repos/{owner}/{repo}/pulls/{n}``
    and check ``head.repo.fork``; that lives in a future revision.
    """
    return "fork=true" in pr_url.lower()


def _build_review_prompt(pr_url: str, diff: str) -> str:
    """Construct the prompt sent to mahavishnu ``pool-route-execute``."""
    truncated = diff[:DIFF_PROMPT_LIMIT_CHARS]
    return (
        "Review the following pull request diff for quality, security, "
        "and convention adherence:\n\n"
        f"PR: {pr_url}\n\n"
        f"Diff:\n{truncated}"
    )


def _queue_for(queue_path: str | Path | None = None) -> DurableQueue:
    """Construct the queue from env or the explicit override."""
    path = queue_path or os.environ.get(QUEUE_PATH_ENV_VAR, DEFAULT_QUEUE_PATH)
    return DurableQueue(path)


async def _dispatch_via_mahavishnu(
    prompt: str,
    idempotency_nonce: str,
    mahavishnu_bin: str | None = None,
) -> dict[str, Any]:
    """Cross-process dispatch via mahavishnu CLI.

    Subprocess rather than in-process import because crackerjack and
    mahavishnu are SEPARATE repos; importing across repos would couple
    them inappropriately. When crackerjack grows an MCP-aware runtime
    this can swap to ``mcp__mahavishnu__pool_route_execute`` for
    observability.

    The C-6 Typer shim exposes ``--idempotency-source <value>`` and
    ``--idempotency-nonce <value>`` as separate flags; this matches
    that interface.

    Returns the parsed JSON stdout. Raises ``RuntimeError`` on non-zero
    return code so callers can label the result metric.
    """
    bin_path = mahavishnu_bin or os.environ.get(
        MAHAVISHNU_BIN_ENV_VAR, DEFAULT_MAHAVISHNU_BIN
    )
    cmd = [
        bin_path,
        "pool-route-execute",
        "execute",
        "--prompt",
        prompt,
        "--pool-selector",
        "least_loaded",
        "--idempotency-source",
        MAHAVISHNU_DISPATCH_IDEMPOTENCY_SOURCE,
        "--idempotency-nonce",
        idempotency_nonce,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"mahavishnu dispatch failed: {stderr.decode()}")
    return json.loads(stdout.decode())


async def _handle_pr_event(
    pr_url: str,
    queue: DurableQueue | None = None,
    *,
    dispatch: Any = _dispatch_via_mahavishnu,
) -> dict[str, Any] | None:
    """Process one PR review event.

    Steps:

    1. Enqueue (idempotent) so background retry can re-attempt.
    2. Fetch the diff via ``fetch_pr_diff``.
    3. Dispatch via mahavishnu (subprocess) to get a review comment.
    4. Post the comment back via ``post_pr_comment``.
    5. Increment per-result metric and observe histogram.

    Returns the API response dict on success, ``None`` on transient
    failure (5xx/429/network). Callers translate ``None`` into "still
    in queue, retry later".
    """
    own_queue = queue is None
    if own_queue:
        queue = _queue_for()
    queue.enqueue(pr_url)

    start = time.monotonic()

    try:
        diff = await fetch_pr_diff(pr_url)
    except GitHubAPIError as exc:
        message = str(exc)
        if "rate limited" in message:
            label = "429"
        elif "auth failure" in message:
            label = "auth"
        elif "network error" in message:
            label = "timeout"
        elif "server error" in message:
            label = "5xx"
        else:
            label = "error"
        PR_REVIEW_POST_TOTAL.labels(result=label).inc()
        if _is_fork_pr(pr_url):
            PR_REVIEW_FORK_PR_TOTAL.labels(result=label).inc()
        logger.warning(
            "GitHub fetch failed; queued for retry",
            extra={"pr_url": pr_url, "error": message},
        )
        return None

    idempotency_nonce = hashlib.sha256(pr_url.encode()).hexdigest()[:32]
    prompt = _build_review_prompt(pr_url, diff)

    try:
        result = await dispatch(prompt, idempotency_nonce)
    except Exception as exc:  # noqa: BLE001 — dispatcher boundary
        PR_REVIEW_POST_TOTAL.labels(result="error").inc()
        if _is_fork_pr(pr_url):
            PR_REVIEW_FORK_PR_TOTAL.labels(result="error").inc()
        logger.exception(
            "review dispatch failed",
            extra={"pr_url": pr_url, "error": str(exc)},
        )
        return None

    try:
        await post_pr_comment(pr_url, result["comment"])
    except GitHubAPIError as exc:
        PR_REVIEW_POST_TOTAL.labels(result="error").inc()
        if _is_fork_pr(pr_url):
            PR_REVIEW_FORK_PR_TOTAL.labels(result="error").inc()
        logger.exception(
            "comment post failed",
            extra={"pr_url": pr_url, "error": str(exc)},
        )
        return None

    PR_REVIEW_DURATION.observe(time.monotonic() - start)
    PR_REVIEW_POST_TOTAL.labels(result="success").inc()
    if _is_fork_pr(pr_url):
        PR_REVIEW_FORK_PR_TOTAL.labels(result="success").inc()
    return {"pr_url": pr_url, "result": result}


async def on_akosha_pattern(event: dict[str, Any]) -> dict[str, Any] | None:
    """Akosha pattern subscription handler.

    Trigger: ``ecosystem.event.received{source="git-monitor"}`` (set in
    ``SKILL_REGISTRY["review_pr"]["trigger"]``). External systems
    (GitHub, Stripe, etc.) publish to Akosha directly via the standard
    Akosha publisher; this consumer reads typed ``payload.data`` fields
    rather than a sanitized string.

    Event shape (per Akosha envelope):

    .. code-block:: json

        {
          "payload": {
            "source": "git-monitor",
            "data": {
              "pr_url": "https://github.com/owner/repo/pull/123"
            }
          }
        }
    """
    payload = event.get("payload", {}) if isinstance(event, dict) else {}
    if not isinstance(payload, dict):
        return None
    source = payload.get("source", "")
    if source != "git-monitor":
        return None

    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None
    pr_url = data.get("pr_url", "")
    if not pr_url:
        logger.debug("no pr_url in event; skipping")
        return None

    return await _handle_pr_event(pr_url)


__all__ = [
    "AKOSHA_PATTERN_TRIGGER",
    "DEFAULT_MAHAVISHNU_BIN",
    "DEFAULT_QUEUE_PATH",
    "MAHAVISHNU_DISPATCH_IDEMPOTENCY_SOURCE",
    "MAHAVISHNU_VERSION_PIN",
    "QUEUE_PATH_ENV_VAR",
    "_build_review_prompt",
    "_dispatch_via_mahavishnu",
    "_handle_pr_event",
    "_queue_for",
    "on_akosha_pattern",
]