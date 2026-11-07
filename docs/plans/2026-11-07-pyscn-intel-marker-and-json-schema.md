---
title: Adopt pyscn >= 1.30 via an Intel-Skipping Dependency Marker
description: PyPI publishes no macOS Intel (x86_64) wheel for pyscn past 1.5.0 and no sdist, so the `pyscn==1.5.0` pin is the only installable option on an Intel Mac and forces every other platform onto a 2025 release. Replacing the pin with an environment marker that skips the pip dependency on Intel macOS, while requiring pyscn >= 1.30 elsewhere, lets non-Intel platforms track current pyscn and lets Intel use the Homebrew build. pyscn 1.30 changed the JSON report to snake_case, so the parser moves to that schema and rejects the legacy one loudly instead of silently reporting zero findings.
audience: crackerjack maintainer
created: 2026-11-07
status: active
role: implementation
topic: dependency-management
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Adopt pyscn >= 1.30 via an Intel-Skipping Dependency Marker

## Policy: No backwards compatibility / legacy support

The pre-1.30 CamelCase report schema is **not supported**. `PyscnJSONParser` reads
the snake_case schema only. A report in the legacy schema raises a `ParsingError`
naming the required pyscn version, rather than parsing to zero findings. There is
no dual-key fallback and no deprecation window.

## Brief (intent-driven)

### Goal

Move crackerjack onto a pyscn dependency that resolves to a current release on every
platform except Intel macOS, where the binary comes from Homebrew.

### Constraints

- Must install a pyscn >= 1.30 on every platform that has a PyPI wheel.
- Must not require a pyscn wheel on Intel macOS, where none exists past 1.5.0.
- Must fail loudly, not silently, when the pyscn in use predates the snake_case
  report schema.
- Must not change any pyscn CLI invocation that crackerjack already issues.

### Failure Conditions (verifier-only)

- If `PyscnJSONParser` returns zero issues for a report whose `complexity` section
  carries `functions` with an entry above the threshold, fail.
- If parsing a CamelCase report does not raise, fail.
- If `pyscn check` or `pyscn analyze` is invoked with a flag the resolved binary does
  not support, fail.
- If `uv.lock` records a pyscn version below 1.30 for a platform that has a wheel,
  fail.
- If the resolved pyscn binary is not the one the operator expects (venv first,
  then PATH in order, skipping any candidate below the 1.30 floor), fail.
- If a pyscn report fails to parse and the gate still reports zero pyscn
  findings, fail — the complexity coverage must not silently disappear.
- If the complexity threshold and the metric it was calibrated against come
  from different pyscn versions, fail — the gate must not report findings
  that are only there because the tool changed its scale.

## Background: why the pin exists and what it costs

PyPI's file index shows `pyscn-1.5.0-py3-none-macosx_10_9_x86_64.whl` is the
**highest** macOS Intel wheel ever published. Every release from 1.5.1 onward ships
`macosx_11_0_arm64` only, and **no sdist is published**, so `pip install pyscn`
cannot be satisfied on an Intel Mac at all — there is nothing to fall back to.

Upstream (Daisuke Yoda, pyscn's author) has stated the Intel wheel will not return.

So `pyscn==1.5.0` is load-bearing on Intel. But it is also a *global* pin: every
platform, and every consumer of the published crackerjack wheel, is held at a 2025
release.

The way out is the one upstream proposed: skip the pip dependency where no wheel
exists, and supply the binary another way.

## What changed

### 1. The dependency marker (`pyproject.toml`)

```toml
"pyscn>=1.30; sys_platform != 'darwin' or platform_machine != 'x86_64'",
```

`uv.lock` now records:

```
{ name = "pyscn", marker = "platform_machine != 'x86_64' or sys_platform != 'darwin'", specifier = ">=1.30" }
```

and resolves pyscn to **1.33.1** for platforms that have a wheel. On Intel macOS
the dependency is simply absent, so the venv carries no pyscn.

### 2. The JSON report schema (`crackerjack/parsers/json_parsers.py`)

pyscn 1.30 switched the JSON report to snake_case. Measured on the same probe file:

| Key | pyscn 1.5.0 | pyscn >= 1.30 |
|---|---|---|
| complexity section | `Functions` | `functions` |
| function item | `Name`, `FilePath`, `StartLine`, `Metrics`, `RiskLevel` | `name`, `file_path`, `start_line`, `metrics`, `risk_level` |
| metrics | `Complexity`, `Edges`, `ExceptionHandlers`, `IfStatements`, `LoopStatements`, `NestingDepth`, `Nodes`, `SwitchCases` | `complexity`, `edges`, `exception_handlers`, `if_statements`, `loop_statements`, `nesting_depth`, `nodes`, `switch_cases` |
| `dead_code` section | already snake_case | already snake_case |
| `clone` section | already snake_case | already snake_case |

Only the **complexity** section changed casing. The `dead_code` and `clone`
sections were already snake_case in 1.5.0, so `_parse_dead_code_section` and
`parse_clone_groups` need no change.

`_parse_complexity_section` now raises a `ParsingError` when it sees a
`complexity.Functions` key, naming the required version. Without that, an old pyscn
would produce a report the parser silently read as zero findings — a hole in the
gate that nothing would flag.

### 3. Binary resolution (`crackerjack/adapters/sast/pyscn.py`)

The adapter invoked `pyscn` by bare name, so it resolved through `PATH` only. The
gate already used the shared `preferred_binary_command` helper (prefer
`./.venv/bin/<tool>`, then `PATH`), so the two paths disagreed. The adapter now uses
the same helper.

`_preferred_binary_command` was renamed to `preferred_binary_command` (and
`_preferred_binary_command_with_report` to `preferred_binary_command_with_report`)
because it now has a consumer outside `crackerjack/config/`.

### 4. The `.pyscn.toml` config key

pyscn >= 1.30 rejects `cbo.enabled`:

```
Warning: .pyscn.toml: unknown configuration key "cbo.enabled"
```

This is an **upstream bug**: `pyscn init` in 1.33.0 writes a `.pyscn.toml` that
contains `[cbo] enabled = true`, and the same binary then rejects that key. The
key was removed from crackerjack's config; the CBO thresholds are still honoured,
and CBO can be driven from the CLI (`--min-cbo`).

### 5. Version-aware binary resolution

The marker removes pyscn from the venv on Intel, which means the binary now
comes from `PATH`. `preferred_binary_command` resolved it with
`shutil.which`, which returns **only the first match**. On this machine that
first match was `~/Projects/mahavishnu/.venv/bin/pyscn` — version **1.5.0**,
left over from the old pin — so the Homebrew 1.33.0 build that the marker
exists to enable was never reached.

`preferred_binary_command_with_min_version` walks **every** candidate (the
project venv first, then each `PATH` entry in order), probes each with
`--version`, and returns the first whose reported version satisfies the floor.
A binary that is too old is *skipped*, not used. When no candidate qualifies
it raises a `RuntimeError` naming every candidate it inspected and the version
each reported.

The probe is cached (`lru_cache`), and the pyscn hook command is built with
`functools.partial` so resolution happens at `get_tool_command()` call time
rather than at module import — this module builds its command table at import,
and probing there would spawn a subprocess on every import.

Every pyscn invocation now goes through the resolver: the quality-gate hook
(`tool_commands.py`), the adapter's `build_command` and `parse_clone_groups`
(`adapters/sast/pyscn.py`), and the clone CLI (`cli/clone_cli.py`, which
previously shelled out to a bare `"pyscn"`).

### 6. The gate must not silently lose complexity coverage

`_extract_issues_via_json_parser` caught every exception from the JSON parser
and fell back to a **text** parser. That fallback cannot read `--json` output,
so a pyscn report that failed to parse degraded to *zero findings* — and a
hook with zero findings passes. The CamelCase guard from section 2 was
therefore not loud in the gate: it became a `logger.warning`.

The fix distinguishes the two reasons a report can fail to parse, because
they need opposite handling:

| cause | recoverable from text output? | handling |
|---|---|---|
| the output is text, not a JSON report | yes | keep the text fallback |
| the report uses a schema this parser cannot read | **no** | fail loudly |

A schema mismatch means the tool is the wrong version, and its findings
cannot be recovered from the text output — so `ToolSchemaError` (a subclass
of `ParsingError`) marks that case, and the hook executor returns it as an
issue so the gate fails and names the cause.

Failing on every parse error would have been the blunt version, and it would
have regressed the text path: `tests/test_hook_executor.py::
test_pyscn_dispatched_through_reporting_tools` exists because the failure
panel once showed 18 lines of cobra help text instead of 1 real finding, and
that path is still worth protecting.

**But the text fallback is itself a fail-open, and the schema split alone
does not close it.** The pyscn hook always runs `pyscn analyze --json`, so
its output is JSON mode — where the text fallback recovers nothing and
returns zero. A zero-finding hook passes. So the fallback is now used only
when it actually recovers text findings; an empty fallback result after a
parse failure means the findings are *unknown*, and that is reported.

Two more silent-zero paths sat in the JSON path itself and are now failures:

- the report was announced but the file is not there — was
  `logger.warning` + `return []`;
- the report could not be read or parsed — was `logger.error` + `return []`.

Both now raise, so they land in the fail-closed handler above. Together the
three paths are the difference between "the gate reports zero because the
code is clean" and "the gate reports zero because nothing was read", and only
the first is a pass.

### 7. The complexity threshold had to be re-calibrated

With pyscn able to read the whole tree for the first time, the complexity gate
reported **19 findings above the threshold of 15** — on code nobody had
changed. Two measurements explain it.

**pyscn >= 1.30 changed its complexity metric.** The same function scores 13
under pyscn 1.5.0 and 23 under pyscn 1.33.0:

```
threshold=  5 1.5.0:  ExtractMethodPattern.match is too complex (13 > 5)
threshold=  5 1.33.0: ExtractMethodPattern.match is too complex (23 > 5)
```

**The threshold of 15 was never actually enforced.** pyscn 1.5.0 could not
parse the repo's PEP 758 `except A, B:` files and said so, then analysed
nothing:

```
Warning: Failed to parse file crackerjack/adapters/_tool_adapter_base.py: syntax errors found in source code
```

Ten files were skipped, and `pyscn check --max-complexity 15` reported **zero**
complexity violations repo-wide even for the files it could parse — because
its metric put the highest function at 13. The gate was green, but it was
green because the tool was looking at a different scale.

So the threshold moves to **25**, which is the value complexipy already
enforces in this repo (`--max-complexity-allowed 25`). Both complexity gates
now express one policy, and no function in the tree exceeds it under the
current metric (19 findings at 15, 3 at 20, 0 at 25). The threshold now lives
in one place — `PYSCN_MAX_COMPLEXITY` in `models/tool_config.py` — instead of
being repeated in the parser default, the adapter settings, the adapter's
`init` and its default config, so the JSON-report path and the `pyscn check`
CLI path cannot drift apart.

## What did NOT change, and why

- **The CLI invocations.** `pyscn check --max-complexity N <files>` and
  `pyscn analyze --json --select clones --clone-threshold T <root>` are supported by
  both versions; 1.33 only *adds* flags.
- **The text-output parser.** `PyscnAdapter._parse_text_output` matches
  `"is too complex"`, and both versions emit the identical line format:
  `path/file.py:1:1: f is too complex (17 > 15)`.
- **The `clone` section parsing.** `clone.clone_pairs` is unchanged across versions.
- **The `dead_code` section parsing.** Already snake_case in 1.5.0.

## Verification

End-to-end against both binaries, feeding each real report through the patched
parser:

```
=== brew-1.33.0 exit=0 reports=1
  parsed issues: 1
    /tmp/pyscn_e2e/brew-1.33.0/cx.py:1 [Priority.MEDIUM] Function 'complex_fn' has cyclomatic complexity 17
  get_issue_count: 1
=== venv-1.5.0 exit=0 reports=1
  parse_json RAISED ParsingError: pyscn report uses the pre-1.30 CamelCase complexity schema
  ('complexity.Functions'). This parser requires pyscn >= 1.30, which emits snake_case
  ('complexity.functions').
```

Unit tests: 88 passed (`tests/adapters/test_pyscn.py`,
`tests/adapters/test_pyscn_adapter.py`, `tests/unit/parsers/test_json_parsers.py`).

Version-aware resolution, measured on this machine with a stale pyscn 1.5.0
first on `PATH`:

```
candidates:
   /Users/les/Projects/mahavishnu/.venv/bin/pyscn
   /usr/local/bin/pyscn
resolved -> /usr/local/bin/pyscn
version  -> pyscn version 1.33.0
```

The integration venv, created from the new lockfile on this Intel Mac, contains
**no pyscn at all** — the marker correctly excludes it — so the Homebrew build
is what the gate runs.

## Out of Scope

- **`pyscn` in other repos' venvs.** The marker only removes pyscn from a venv that
  installs crackerjack. Another repo's venv that still carries pyscn 1.5.0 stays
  on disk until that repo is re-locked, but it can no longer *shadow* a usable
  pyscn: the version-aware resolver skips it and picks the next candidate that
  satisfies the floor.
- **The `summary` section's differing complexity average.** pyscn 1.5.0 reported
  `Complexity: 0/100 (avg: 17.x)` for the same file where 1.33 reported
  `60/100 (avg: 7.x)`. The per-function complexity value is identical (17 in both),
  so the threshold semantics crackerjack relies on are unchanged; the summary-level
  score is computed differently and crackerjack does not consume it.
- **Upstream's `cbo.enabled` bug.** Reported to pyscn, not fixed here.
- **Refactoring the 19 functions the re-calibrated metric exposed.** Under
  pyscn >= 1.30 the highest function in the tree scores 23; the threshold is
  set to 25 to match complexipy, so nothing is reported. Tightening it below
  25 means refactoring those functions, which is a separate piece of work.
