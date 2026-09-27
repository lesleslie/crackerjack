---
name: review-pr
description: Use ONLY when the user explicitly types `/crackerjack:review-pr` or selects this Skill from the picker to wire the C-13 review-pr trigger into a running session. Do not auto-trigger. The skill subscribes to the Akosha pattern `ecosystem.event.received{source='git-monitor'}` (NOT a Mahavishnu webhook), fetches the PR diff via the `CRACKERJACK_GITHUB_TOKEN` env var, dispatches a code-review prompt to Mahavishnu's `pool-route-execute` (with idempotency), and posts the review back as a PR comment. Routes through `mcp__crackerjack__crackerjack_list_skills` then `crackerjack.skills.review_pr.on_akosha_pattern`.
allowed-tools: mcp__crackerjack__crackerjack_list_skills, mcp__crackerjack__crackerjack_get_skill, Read
---

# review-pr

## When to use

This Skill wires the C-13 review-pr trigger into a running session.
C-13 ties together C-5 (mahavishnu `safe_publish` singleton) + C-6
(idempotent dispatch) + the niche filter (no Mahavishnu webhook) +
Akosha as the cross-system event bus. It is the "consume Akosha events
and act on them" half of the Bodai event flow.

Use this Skill when:

- The user says "wire up PR review", "register the review-pr skill", or
  "subscribe to git-monitor events"
- The user wants to verify the C-13 contract (Akosha pattern trigger,
  no webhook intake, env-var reference for the GitHub token)

## What it does

1. Subscribes to the Akosha pattern
   `ecosystem.event.received{source="git-monitor"}`.
2. On each matching event, extracts the structured ``pr_url`` from
   ``payload.data`` (NOT a sanitized string).
3. Enqueues the PR URL in the sqlmodel-backed durable queue.
4. Fetches the diff via `crackerjack.skills.github_client.fetch_pr_diff`.
5. Dispatches a code-review prompt to Mahavishnu's
   `pool-route-execute execute --idempotency-source
   crackerjack.review_pr`.
6. Posts the review back as a PR comment via
   `crackerjack.skills.comment_poster.post_pr_comment`.
7. Increments four metrics:
   - `pr_review_post_total{result}`
   - `pr_review_duration_seconds_bucket`
   - `github_api_quota_remaining`
   - `pr_review_fork_pr_total{result}`

## Hard policy (from plan)

- **No webhook intake.** Akosha pattern subscription REPLACES any
  Mahavishnu webhook trigger; external systems publish to Akosha
  directly.
- **CRACKERJACK_GITHUB_TOKEN is referenced, not raw.** Settings hold
  the env-var name (`crack.review_pr.api_key_env`); the value itself
  lives in the operator's shell rc.
- **Version-pin to `mahavishnu >= 0.29`** — C-5's `safe_publish` and
  C-6's `IdempotencyOptions` were first published in 0.29.
- **Pre-1.0 zero backcompat** — replace, don't extend.

## Rollback

- Soft: set `crack.review_pr.enabled: false` in settings/local.yaml.
- Hard: `git revert <commit-sha>` to drop the skill entirely.