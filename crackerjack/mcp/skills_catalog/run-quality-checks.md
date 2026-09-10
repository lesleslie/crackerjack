---
name: run-quality-checks
description: Use ONLY when the user explicitly types `/crackerjack:run-quality-checks` or selects this Skill from the picker to run the full Crackerjack quality workflow. Do not auto-trigger. Routes through `mcp__crackerjack__crackerjack_run` to surface all configured hooks (ruff, mypy, pyright, bandit, complexipy, pytest). Use when the user says "run quality checks", "run crackerjack", "is this code clean", or "what does crackerjack say about this repo".
allowed-tools: mcp__crackerjack__crackerjack_run, mcp__crackerjack__get_comprehensive_status, Read
---

# run-quality-checks

## When to use

This Skill is the right entry point when the user wants to run the
full Crackerjack quality suite against the current working tree:

- "Run quality checks"
- "What does crackerjack think of this code?"
- "Run all the checks"
- "Is this PR clean?"

The Skill runs the full hook sequence in order:

1. `ruff check --fix --unsafe-fixes` (fast_hooks stage)
2. `ruff format` (formatter)
3. `mypy` (strict)
4. `pyright` (strict)
5. `bandit` (security)
6. `complexipy` (complexity)
7. `pytest` with coverage

A failure at any stage halts the run (fail-fast). The Skill returns the
exit code + a summary of which stage failed and the relevant error
output.

## What the tool does

`mcp__crackerjack__crackerjack_run` triggers the full Crackerjack
workflow as a subprocess. Each hook has a timeout, and the overall
workflow has a per-stage timeout (default 300s per hook).

The Skill calls `crackerjack_run` with no special flags; the standard
hook order is fine for most uses. For faster feedback on a specific
category, call directly with `--skip-hooks` or a specific subset.

## When NOT to use

- For per-tool queries, prefer `mcp__crackerjack__crackerjack_run --only <hook>`.
- For pre-commit checks only, use `crackerjack run -p pre-commit`.
- For just ruff fast_hooks without full coverage: `crackerjack fast-hooks`.

## Failure modes and how to handle them

- **Hook timeout**: the per-stage timeout is hit. Surface the partial
  output to the user; suggest they run the failing hook directly with
  a longer timeout.
- **Tool not installed**: e.g. `bandit` or `pyright` missing from the
  venv. The output will say "command not found"; surface verbatim.
- **Coverage threshold not met**: 89.0% gate per CLAUDE.md. Show the
  coverage report and the uncovered modules.
- **Quality score < 80**: the `min_score` gate (per settings/mahavishnu.yaml
  in related repos). Surface the score and which dimensions fell short.

## Example flow

User: "Is this branch clean?"

Skill action:

```python
result = await mcp__crackerjack__crackerjack_run()
if result["exit_code"] != 0:
    print(f"crackerjack FAILED at stage: {result['failed_stage']}")
    print(result["stage_output"][:2000])
else:
    print(f"crackerjack PASSED. Quality score: {result['quality_score']}")
```

Surface the failing stage's output verbatim; do not paraphrase.
