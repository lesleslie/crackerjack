---
name: smart-error-analysis
description: Use ONLY when the user explicitly types `/crackerjack:smart-error-analysis` or selects this Skill from the picker to surface common Crackerjack fix-failure patterns. Do not auto-trigger. Routes through `mcp__crackerjack__smart_error_analysis` with `use_cache=True` for the cached local error-pattern path. Use when the user asks "what keeps breaking in the test suite?", "which hook fails most often?", or "is there a pattern in the recent failures?"
allowed-tools: mcp__crackerjack__smart_error_analysis, Read
---

# smart-error-analysis

## When to use

This Skill is the right entry point when the user wants to surface
patterns in recent Crackerjack failures rather than fix a single
issue:

- "What keeps breaking?"
- "Which hook fails most often?"
- "Any pattern in the recent failures?"
- "What did the cache return?"

The Skill returns aggregated fix-failure records from the local
Crackerjack error-pattern cache and surfaces the most frequent patterns
in the last 30 days.

## What the tool does

`mcp__crackerjack__smart_error_analysis` reads accumulated fix-failure
records from the local error-pattern cache. The `use_cache=True` flag
serves the cached result; the first call per session triggers a fresh
aggregation.

The output includes:

- Top N failure fingerprints (e.g. `HookExecutionTimeout:pyright`)
- Frequency (count + percentage)
- Most recent occurrence timestamp
- Suggested remediation (when available in the cache)

## When NOT to use

- For real-time hook failures during a current run, prefer the
  fresh `crackerjack_run` output.
- For brand-new errors not yet in the cache, this Skill returns
  empty results — surface "no cached patterns found" and suggest a
  fresh `crackerjack_run`.

## Failure modes and how to handle them

- **Cache miss on first call**: response includes `cached=False`; the
  caller should retry after ~30s. Surface to the user as "warming
  up the cache".
- **Cache unavailable**: response includes `status="error"` with a
  `message` describing the failure. Surface verbatim; do not retry
  silently.
- **Stale cache**: if `cached=True` but `cache_age_seconds > 300`,
  surface "cache stale; call with use_cache=False to refresh".

## Example flow

User: "What keeps breaking in crackerjack?"

Skill action:

```python
result = await mcp__crackerjack__smart_error_analysis(use_cache=True)
if not result["cached"]:
    print("warming up the cache; retry in ~30s")
elif result["patterns"]:
    for p in result["patterns"][:5]:
        print(f"{p['fingerprint']}: {p['count']} occurrences (last: {p['last_seen']})")
else:
    print("no cached failure patterns")
```

Surface the top 5 patterns to the user; cite the timestamps.
