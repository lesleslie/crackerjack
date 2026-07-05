"""Precommitment hypothesis lock CLI subcommand.

Spec #2 (precommitment-hypothesis-lock): lock a hypothesis before
execution so post-hoc rationalization is detectable.

Usage:
    crackerjack precommit lock --claim "..." --falsify "..." --success "..."
"""

from __future__ import annotations

import json
import sys
import typing as t
from datetime import UTC, datetime

import typer

from crackerjack.core.precommitment import (
    Hypothesis,
    HypothesisLock,
    InMemoryLockStore,
    LockStore,
    verify_lock,
)

app = typer.Typer(
    name="precommit",
    help="Lock a hypothesis before execution (Spec #2: precommitment-hypothesis-lock).",
    add_completion=False,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _shared_store() -> LockStore:
    """Return the active lock store. v0 ships in-memory only."""
    return InMemoryLockStore()


@app.command("lock")
def lock_command(
    claim: str = typer.Option(
        ...,
        "--claim",
        help="The claim being locked (the hypothesis).",
    ),
    falsify: str = typer.Option(
        ...,
        "--falsify",
        help="Criteria that would falsify this hypothesis.",
    ),
    success: str = typer.Option(
        ...,
        "--success",
        help="Criteria that would confirm this hypothesis.",
    ),
    confidence: float = typer.Option(
        0.5,
        "--confidence",
        min=0.0,
        max=1.0,
        help="Confidence in [0.0, 1.0] (default: 0.5).",
    ),
    verify_with: str | None = typer.Option(
        None,
        "--verify-with",
        help="Optional JSON result to verify against the locked criteria.",
    ),
) -> None:
    """Lock a hypothesis and (optionally) verify a result against it."""
    hypothesis = Hypothesis(
        claim=claim,
        falsification_criteria=falsify,
        success_criteria=success,
        confidence=confidence,
        locked_at=_utc_now_iso(),
    )
    lock = HypothesisLock.lock(hypothesis)

    store = _shared_store()
    store.put(lock)

    payload: dict[str, t.Any] = {
        "status": "locked",
        "lock_id": lock.lock_id,
        "signature": lock.signature,
        "hypothesis": {
            "claim": hypothesis.claim,
            "falsification_criteria": hypothesis.falsification_criteria,
            "success_criteria": hypothesis.success_criteria,
            "confidence": hypothesis.confidence,
            "locked_at": hypothesis.locked_at,
        },
    }

    if verify_with is not None:
        try:
            result_obj = json.loads(verify_with)
        except json.JSONDecodeError as exc:
            typer.echo(
                f"[red]error: --verify-with must be valid JSON: {exc}[/red]",
                err=True,
            )
            raise typer.Exit(2) from exc
        passed = verify_lock(lock, result_obj)
        payload["verify"] = {
            "result": result_obj,
            "satisfied": passed,
        }
        payload["status"] = "verified" if passed else "falsified"

    typer.echo(json.dumps(payload, indent=2, sort_keys=True))

    if verify_with is not None and not payload["verify"]["satisfied"]:
        raise typer.Exit(1)

    sys.exit(0)


__all__ = ["app"]
