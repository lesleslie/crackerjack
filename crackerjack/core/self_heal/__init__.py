"""Three-layer self-heal protocol (L1/L2/L3).

Spec #4: three-layer-self-heal (Phase 2).

L1 (transient retry): bounded exponential backoff; raises ``L1Exhausted``
when all attempts fail.
L2 (no-op stub): returns ``"noop_recovery"`` without invoking Claude.
Regression-tested after the C4 fix.
L3 (long-term rule extraction): appends ``RuleRecord`` to an in-memory
``RuleStore`` so future runs can match patterns to recovery hints.

The Dhara substrate (audit log table) is currently ``sql_blocked``, so the
rule store is in-memory only. Persistent wiring follows once the substrate
unblocks.
"""

from __future__ import annotations

from crackerjack.core.self_heal.l1_retry import (
    L1Exhausted,
    L1Retry,
    l1_retry,
    retry_with_backoff,
)
from crackerjack.core.self_heal.l2_noop import (
    L2Noop,
    l2_noop,
)
from crackerjack.core.self_heal.l3_rule_store import (
    RuleRecord,
    RuleStore,
    apply_rule,
    extract_rule,
    record_rule,
)

__all__ = [
    # L1
    "L1Exhausted",
    "L1Retry",
    "l1_retry",
    "retry_with_backoff",
    # L2
    "L2Noop",
    "l2_noop",
    # L3
    "RuleRecord",
    "RuleStore",
    "apply_rule",
    "extract_rule",
    "record_rule",
]