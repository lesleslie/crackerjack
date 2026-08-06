---
title: Crackerjack Ruff Fix Policy Design
status: proposed
date: 2026-08-06
authors: brainstormsession
related:
  - docs/CLI_REFERENCE.md
  - crackerjack/config/tool_commands.py
  - crackerjack/core/preflight.py
  - crackerjack/core/autofix_coordinator.py
  - crackerjack/adapters/format/ruff.py
  - crackerjack/services/config_template.py
  - pyproject.toml
---

# Crackerjack Ruff Fix Policy Design

## 1. Context and problem

Ruff 0.16.0 expanded its default enabled rule set from 59 rules to 413 rules. Crackerjack's working lock file now selects Ruff 0.16.0, and `ruff check ./crackerjack` reports 1249 findings on the current working tree (721 BLE001, 164 DTZ005, 92 TRY401, 79 SIM102, 46 RUF012, 34 B008, 29 PLW1510, ...).

While investigating that spike, four conflicting Ruff fix-safety defaults were found in the repository:

1. `crackerjack/config/tool_commands.py:228-235` hardcodes `--unsafe-fixes` for the `ruff-check` fast-hook and bypasses `SafeCodeModifier`.
2. `crackerjack/core/preflight.py` exposes `PreflightConfig.ruff_unsafe_fixes` (default `False`) but its `ruff_check` wrapper still passes `--fix` to the whole package on every run.
3. `crackerjack/services/config_template.py:62` emits `"unsafe-fixes": True` into scaffolded downstream projects, which silently enables unsafe fixes for any developer who runs Ruff directly.
4. Several adapter paths are correctly read-only: `agents/validation_coordinator.py`, `ai_fix/output_validator.py` (`ruff_sanity_check`), the `all_commands` dry-run tuple, and `shell/adapter.py` `_run_lint`. These must remain read-only.

The team wants to clear the 1249 findings efficiently, but without turning a quality-gate command into an implicit, hard-to-review code rewriter.

## 2. Goals and non-goals

### Goals

- Make the default Ruff behavior safe, deterministic, and easy to review.
- Allow operators to clear the 1249-finding backlog in a small number of reviewable commits.
- Make unsafe fixes an explicit, opt-in, rollback-friendly operation.
- Restore a single source of truth for "should Ruff write files in this invocation?".

### Non-goals

- Re-tuning the project's rule set beyond what is required to converge the backlog.
- Restructuring the agent subsystem.
- Rewriting `autofix_coordinator.py` end-to-end.
- Adding new dependency integrations.

## 3. Policy decision

Crackerjack's normal `crackerjack run` quality path shall:

- Default to **safe fixes only** via `ruff check --fix` (no `--unsafe-fixes`).
- Never pass `--unsafe-fixes` without an explicit operator opt-in.
- Never mutate CI runs (`--no-fix`).
- Expose `--diff` / `--preview` so the operator can review the proposed patch before any rewrite.
- Pin Ruff intentionally so future default-rule expansions do not create another surprise.

Unsafe fixes become a separate explicit command (see Section 4.4).

## 4. Design

### 4.1 Default local `crackerjack run` (safe fixes only)

Change the default `ruff-check` hook in `crackerjack/config/tool_commands.py:228-235` from:

```text
ruff check --output-format json --fix --unsafe-fixes ./crackerjack
```

to:

```text
ruff check --output-format json --fix ./crackerjack
```

Ruff's documented behavior is that `--fix` applies safe fixes only, and `--unsafe-fixes` is the only flag that opts into unsafe rewrites. See the Ruff [fix-safety documentation](https://docs.astral.sh/ruff/linter/#fix-safety).

### 4.2 CI and quality-gate runs (read-only)

CI invocations shall use `ruff check --no-fix --output-format json ./crackerjack` and fail on remaining violations. CI must never rewrite the checkout; reviewers must be able to assume the diff under review is the diff that was tested.

Concretely:

- The `all_commands` tuple in `crackerjack/core/autofix_coordinator.py:1953-1955` already uses `--check` and `--no-fix`. That tuple stays as-is.
- The `phase_coordinator.py:1852` exclusion of `{"ruff-check", "ruff"}` from phase gating is left in place for now; the policy change above removes the unsafe mutation pathway without requiring a phase-gate change. A follow-up may revisit whether ruff output should flow through the same phase gate as other tools.

### 4.3 Preview path (no mutation)

Add or expose a preview verb that uses `ruff check --diff ./crackerjack`. Ruff documents that `--diff` exits 1 when fixes would be applied and does not write files. See the Ruff [CLI documentation](https://docs.astral.sh/ruff/cli/).

Suggested user flow:

```text
crackerjack run --preview      # inspect proposed safe-fix diff
crackerjack run                # apply safe fixes
```

### 4.4 Explicit unsafe-fix opt-in

Add a single, unmistakable opt-in for unsafe rewrites, for example:

```text
crackerjack run --allow-unsafe-fixes
```

or, preferably, a separate cleanup command:

```text
crackerjack clean --unsafe
```

Implementation notes:

- This flag is the *only* path that may emit `--unsafe-fixes`. No other site may hardcode it.
- The default value of `PreflightConfig.ruff_unsafe_fixes` remains `False`.
- When the flag is set, route the invocation through `SafeCodeModifier` so per-file `.bak` siblings are produced before any rewrite. See `crackerjack/core/file_lifecycle.py:85-114` and `crackerjack/services/safe_code_modifier.py:201-242`.
- The `ruff-check` command template in `tool_commands.py` is the public hook surface; it must read from `HookSettings` rather than embed the flag in the command string.

### 4.5 Generated project configuration (downstream supply chain)

`crackerjack/services/config_template.py:62` currently emits `"unsafe-fixes": True` into the scaffolded `pyproject.toml`. This is a supply-chain leak: a developer running Ruff directly in a generated project will get unsafe fixes even if they never invoke Crackerjack.

Flip that to `"unsafe-fixes": False` so the scaffolded config matches Crackerjack's own default.

### 4.6 Fix exit-code handling

`crackerjack/core/preflight.py:135-143` and surrounding logic must distinguish Ruff exit codes:

- `0` — no remaining violations, or all eligible violations were fixed.
- `1` — violations remain, or the chosen policy intentionally reports applied fixes.
- `2` — Ruff internal, configuration, or parse error. Must be surfaced; never silently accepted as a clean quality run.

The current `result.returncode in (0, 1)` pattern at `preflight.py:165` is acceptable for codes 0/1 only if code 2 is explicitly rejected and surfaced in the run report.

### 4.7 Working-tree guard

Before applying any `--fix` (safe or unsafe), the wrapper must check the working-tree state. If the tree is dirty and the operator did not pass an override, the wrapper must refuse to run and emit a clear error pointing to `git stash` or a `--force` flag.

Suggested implementation hook: `crackerjack/services/git_cleanup_service.py:95-105` already exposes `_validate_working_tree_clean`. Wire that as a precondition for any `--fix` invocation. Tests should cover both the refusal and the override paths.

### 4.8 Ruff version pinning

Change the dependency declaration in `pyproject.toml:54` from:

```toml
ruff>=0.15.18
```

to an exact pin:

```toml
ruff==0.16.0
```

with the corresponding `uv.lock` update as a separate, reviewable change. The pin is the floor for reproducible CI; it is not a substitute for safe-fix defaults.

### 4.9 What must NOT change

These paths are correctly read-only or correctly scoped today and must remain so:

- `crackerjack/ai_fix/output_validator.py:106-141` — `ruff_sanity_check` is a runtime-rules correctness gate.
- `crackerjack/agents/validation_coordinator.py:83-108` — read-only JSON validation.
- `crackerjack/agents/formatting_agent.py:127-153` — already safe (no `--unsafe-fixes`).
- `crackerjack/agents/refactoring_agent.py:1550-1563` — single-file format.
- `crackerjack/agents/type_error_specialist.py:778-790` — single-file format.
- `crackerjack/agents/import_optimization_agent.py:938-941` — regex only, no subprocess.
- `crackerjack/ai_fix/code_post_processor.py:14-57` — `stdin` format on AI output.
- `crackerjack/ai_fix/fix_runner.py:115` and `sandboxed_dispatcher.py:46` — string label only.
- `crackerjack/ai_fix/output_validator.py:106-141` and `ci_feedback.py` — no subprocess / read-only.
- `crackerjack/shell/adapter.py` `_run_lint` (`ruff check`, `ruff format --check`) — already read-only.

## 5. Tests

Add or extend the following tests:

- `tests/unit/core/test_preflight.py::test_tool_commands_respects_hook_settings_unsafe_fixes` — assert that when `HookSettings.ruff_unsafe_fixes=False`, `tool_commands.py:228-235` emits no `--unsafe-fixes`.
- `tests/unit/adapters/test_ruff_adapter.py::test_unsafe_only_auto_promotes_fix` — assert that `adapters/format/ruff.py:146-150` either raises or auto-promotes when `unsafe_fixes=True` without `fix_enabled=True`.
- `tests/unit/services/test_safe_code_modifier.py::test_unsafe_creates_bak_sibling` — assert that unsafe-fix invocations produce per-file `.bak` siblings.
- `tests/unit/services/test_git_cleanup.py::test_dirty_tree_refuses_fix` — assert the working-tree guard.
- `tests/unit/cli/test_options.py::test_unsafe_flag_threaded_to_preflight` — assert the CLI flag is plumbed through.
- `tests/unit/core/test_preflight.py::test_exit_code_routing` — assert that Ruff exit code `2` is surfaced, not silently accepted.
- `tests/fixtures/ruff_unsafe_diff_golden.txt` plus `tests/unit/core/test_ruff_unsafe_golden.py` — golden-diff test for the unsafe-fix output. Must come with a documented `--update-golden` workflow and a human-bless step.

## 6. Documentation

- Add a subcommand × fix-level matrix to `docs/CLI_REFERENCE.md`.
- Add a "Safe vs. Unsafe Fixes" subsection to `crackerjack/hooks/README.md`.
- Add a single `CHANGELOG.md` entry mirroring the historical enable-unsafe-fixes line.
- Resolve the `services/config_template.py:62` divergence in `docs/CONFIG_CONSOLIDATION_AUDIT.md:729`.
- Add the new design document under `docs/superpowers/specs/`.

## 7. Rollout

1. **Stage 0 — Stop the bleed (single commit)**: drop `--unsafe-fixes` from `tool_commands.py:228-235`; flip `config_template.py:62` to `False`. No behavior change for the safe path.
2. **Stage 1 — Configuration surface**: add `HookSettings.ruff_unsafe_fixes: bool = False`, `HookDefinition.allow_unsafe_fixes: bool = False`, and CLI flags `--allow-unsafe-fixes` / `--safe-only` next to `-s/--skip-hooks`.
3. **Stage 2 — Wire settings through**: replace direct `preflight.py:176-180` field lookup with `HookSettings` lookup; fix the silent no-op branch in `adapters/format/ruff.py:146-150`; reconcile `shell/adapter.py` banner with behavior; fix the phantom `ruff-isort` reference in `services/profiler.py:101`.
4. **Stage 3 — Rollback and dirty-tree guard**: route every unsafe-fix invocation through `SafeCodeModifier`; add a `crackerjack rollback-last-fixes` command; wire `_validate_working_tree_clean()` as a precondition for any `--fix` invocation.
5. **Stage 4 — Exit semantics and pinning**: replace `preflight.py:135-143` `subprocess.run(check=False)` with explicit 0/1/2 handling; pin `pyproject.toml:54` to `ruff==0.16.0` with hash-pinned `uv.lock` entry; add the golden-diff test.
6. **Stage 5 — Docs and changelog**: docs/CLI_REFERENCE.md, hooks/README.md, CHANGELOG.md, CONFIG_CONSOLIDATION_AUDIT.md, and `docs/superpowers/specs/`.

## 8. Fastest path through the 1249-finding backlog

The policy rollout above is staged so the immediate throughput story is:

1. `crackerjack run --preview` (uses `--diff`, no mutation) — review the full proposed safe-fix patch.
2. `crackerjack run` — apply safe fixes only.
3. `crackerjack run --allow-unsafe-fixes` — apply the unsafe remainder with per-file `.bak` siblings and a clear review signal.
4. `git restore` or `crackerjack rollback-last-fixes` if tests fail.

This drains the backlog in 2-3 reviewable commits with a full audit trail, without changing the safe-by-default contract for ordinary invocations.

## 9. Open questions

- Should the explicit unsafe command be a new verb (`crackerjack clean --unsafe`) or a flag on the existing run command (`crackerjack run --allow-unsafe-fixes`)? The decision is a UX choice and should be confirmed with the team before Stage 1.
- Should the working-tree guard be a hard refusal or a warning with an override flag? The hard-refusal path is safer; the warning path is faster. Default to hard refusal, allow override via `--allow-dirty`.
