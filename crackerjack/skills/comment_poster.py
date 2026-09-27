"""Posts review comments back to GitHub PRs.

A thin re-export so the review-pr handler imports ``post_pr_comment``
from a domain-named module (matching the plan's file layout) rather
than the lower-level ``github_client``. All behaviour lives in
:func:`crackerjack.skills.github_client.post_pr_comment`.
"""

from __future__ import annotations

from crackerjack.skills.github_client import GitHubAPIError, post_pr_comment

__all__ = ["GitHubAPIError", "post_pr_comment"]
