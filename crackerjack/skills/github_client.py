"""GitHub API client — fetches PR diffs via httpx2.

The token is referenced via the ``CRACKERJACK_GITHUB_TOKEN`` env var;
the value is NEVER hard-coded. ``crackerjack.settings.ai.github.api_key_env``
holds the env-var name so operators can rotate by changing settings, not
by editing source.

Why httpx2 (and not the upstream ``httpx``): crackerjack pins ``httpx2``
(see ``pyproject.toml`` and ``crackerjack/skills/health.py``). The fork
keeps the public API identical, so callers ``import httpx2 as httpx``.

Test seam: tests patch ``crackerjack.skills.github_client._client_get``
and ``_client_post`` with stubs returning ``httpx2.Response``-shaped
objects. respx upstream's ``isinstance(httpx.Response)`` check rejects
httpx2.Response instances, so we use the same seam pattern as
``crackerjack/services/mahavishnu_discovery.py``.
"""
from __future__ import annotations

import os
from typing import Any

import httpx2 as httpx

from crackerjack.skills.review_metrics import GITHUB_API_QUOTA_REMAINING

GITHUB_TOKEN_ENV = "CRACKERJACK_GITHUB_TOKEN"
DEFAULT_TIMEOUT_SECONDS = 30.0
USER_AGENT = "crackerjack-review-pr/1.0"


class GitHubAPIError(Exception):
    """Raised on GitHub API failures (5xx, 429, auth, network, missing token)."""


# Module-level seams for tests. Production code calls these through
# the bound helpers below; tests override them with stub callables
# that return ``httpx2.Response``-shaped objects.
_client_get: Any = None
_client_post: Any = None


def _install_default_seam() -> None:
    """Bind ``_client_get``/``_client_post`` at import time (one-time)."""
    global _client_get, _client_post
    if _client_get is None:
        _client_get = httpx.AsyncClient.get
    if _client_post is None:
        _client_post = httpx.AsyncClient.post


_install_default_seam()


def _parse_pr_url(pr_url: str) -> tuple[str, str, str] | None:
    """Return (owner, repo, number) or None if the URL is malformed."""
    stripped = pr_url.replace("https://github.com/", "").rstrip(".diff")
    parts = stripped.split("/")
    if len(parts) < 4 or parts[2] != "pull":
        return None
    return parts[0], parts[1], parts[3]


def _diff_url_for(pr_url: str) -> str:
    """Convert a PR URL to its ``.diff`` URL (idempotent)."""
    return pr_url if pr_url.endswith(".diff") else f"{pr_url}.diff"


def _update_quota_from_headers(headers: Any) -> None:
    """Read ``x-ratelimit-remaining`` (if present) and store as a Gauge.

    GitHub emits the header on every authenticated API response; missing
    or unparseable values are ignored so a 401 path doesn't raise.
    """
    try:
        remaining = headers.get("x-ratelimit-remaining")
    except AttributeError:
        return
    if remaining is None:
        return
    try:
        GITHUB_API_QUOTA_REMAINING.set(float(remaining))
    except (TypeError, ValueError):
        return


def _status_text(response: Any) -> tuple[int, str]:
    """Read status_code + text off an httpx2.Response-shaped object."""
    status = getattr(response, "status_code", 0)
    text = getattr(response, "text", "")
    return status, (text or "")


async def fetch_pr_diff(pr_url: str) -> str:
    """Fetch the raw diff for a pull request.

    Raises:
        GitHubAPIError: on missing token, 4xx, 5xx, 429, or network
            failure. Callers (``review_pr.py``) translate this into a
            queue retry or a metrics-label increment.
    """
    token = os.environ.get(GITHUB_TOKEN_ENV)
    if not token:
        raise GitHubAPIError(f"{GITHUB_TOKEN_ENV} not set")

    diff_url = _diff_url_for(pr_url)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": USER_AGENT,
    }

    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await _client_get(client, diff_url, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"network error: {exc}") from exc

    _update_quota_from_headers(getattr(response, "headers", {}))
    status, text = _status_text(response)

    if status == 429:
        raise GitHubAPIError(f"rate limited: {status}")
    if status >= 500:
        raise GitHubAPIError(f"server error: {status}")
    if status == 401:
        raise GitHubAPIError("auth failure: 401")
    if status >= 400:
        raise GitHubAPIError(f"client error {status}: {text[:200]}")

    return text


async def post_pr_comment(pr_url: str, body: str) -> dict[str, Any]:
    """Post ``body`` as a comment on the PR; return the response JSON.

    Raises:
        GitHubAPIError: on missing token, malformed URL, 4xx, or 5xx.
    """
    token = os.environ.get(GITHUB_TOKEN_ENV)
    if not token:
        raise GitHubAPIError(f"{GITHUB_TOKEN_ENV} not set")

    parsed = _parse_pr_url(pr_url)
    if parsed is None:
        raise GitHubAPIError(f"malformed PR URL: {pr_url}")
    owner, repo, number = parsed

    api_url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/issues/{number}/comments"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = {"body": body}

    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await _client_post(
                client,
                api_url,
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"network error: {exc}") from exc

    status, text = _status_text(response)
    if status >= 400:
        raise GitHubAPIError(
            f"comment post failed {status}: {text[:200]}"
        )

    try:
        return dict(response.json())
    except (ValueError, AttributeError):
        return {}


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "GITHUB_TOKEN_ENV",
    "GitHubAPIError",
    "USER_AGENT",
    "_diff_url_for",
    "_parse_pr_url",
    "fetch_pr_diff",
    "post_pr_comment",
]