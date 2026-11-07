---
status: wired
role: lifecycle
topic: dependency-management
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# pyscn Intel Marker and Version-Aware Binary Resolution

## Summary

Crackerjack requires pyscn >= 1.30 and obtains it through a dependency
marker that skips the pip dependency on Intel macOS, where PyPI publishes no
wheel and no sdist past 1.5.0. The binary therefore comes from Homebrew, and
a new version-aware resolver picks it out of `PATH` even when an unrelated
project's venv holds an older pyscn earlier on the path. The pyscn JSON
parser reads the >= 1.30 snake_case report schema and fails loudly when a
report cannot be parsed. Wired into the `pyscn` quality-gate hook, the
`PyscnAdapter`, and the clone CLI.

## Why

- **The `pyscn==1.5.0` pin was load-bearing on Intel and a global tax
  everywhere else.** PyPI's highest macOS Intel wheel is
  `pyscn-1.5.0-py3-none-macosx_10_9_x86_64.whl`; every release from 1.5.1
  ships `macosx_11_0_arm64` only, and no sdist is published, so `pip install
  pyscn` cannot be satisfied on an Intel Mac at all. The Homebrew formula
  declares no bottles and compiles the Go CLI from source, so it carries no
  architecture constraint.
- **`shutil.which` returns only the first match, so the Homebrew build was
  unreachable.** Measured on this machine with a stale pyscn 1.5.0 first on
  `PATH`: candidates were
  `/Users/les/Projects/mahavishnu/.venv/bin/pyscn` and
  `/usr/local/bin/pyscn`, and the old resolver returned the 1.5.0 one —
  the build the marker exists to enable was never selected.
- **The complexity gate was blind, not green.** pyscn 1.5.0 could not parse
  the repo's PEP 758 `except A, B:` files and said so, skipping 10 of them
  (`Warning: Failed to parse file ...: syntax errors found in source code`),
  and reported zero complexity violations repo-wide.
- **An unparsable report degraded to zero findings and the hook still
  passed.** `_extract_issues_via_json_parser` caught every parser exception
  and fell back to a text parser that cannot read `--json` output, so the
  gate lost its complexity coverage without failing.
- **Three silent-zero paths made "unreadable" look like "clean".** The JSON
  parser returned zero when the announced report was missing, and when it
  could not be read or parsed; the text fallback returned zero for `--json`
  output. A zero-finding hook passes, so each of those was a way for the
  gate to lose its complexity coverage without failing.

## What is delivered

- **`pyproject.toml`** — `"pyscn==1.5.0"` becomes
  `"pyscn>=1.30; sys_platform != 'darwin' or platform_machine != 'x86_64'"`;
  `uv.lock` records the marker and resolves pyscn 1.33.1 for platforms that
  have a wheel.
- **`crackerjack/config/tool_commands.py`** —
  `preferred_binary_command_with_min_version()` walks every candidate (the
  project venv first, then `PATH` in order), probes each with `--version`,
  and returns the first that satisfies the floor; a binary that is too old
  is skipped, not used. The probe is cached, and the `pyscn` hook command is
  built with `functools.partial` so resolution happens at call time rather
  than at module import.
- **`crackerjack/parsers/json_parsers.py`** — `PyscnJSONParser` reads the
  snake_case schema (`complexity.functions`, `metrics.complexity`, `name`,
  `file_path`, `start_line`, `risk_level`) and raises a `ParsingError`
  naming the required version when it meets the pre-1.30 CamelCase schema.
- **`crackerjack/parsers/factory.py`** — `ToolSchemaError`, a subclass of
  `ParsingError`, marking the one failure mode that is not recoverable: a
  report whose schema this parser cannot read means the tool is the wrong
  version, and its findings cannot be recovered from the text output.
- **`crackerjack/parsers/json_parsers.py`** — the pyscn JSON parser raises
  instead of returning zero when the announced report is missing or
  unreadable. A zero-finding hook passes, so "the findings are unknown" and
  "there were no findings" must not look the same.
- **`crackerjack/executors/hook_executor.py`** — the pyscn path fails closed.
  A `ToolSchemaError`, or any parse failure the text fallback cannot
  recover findings from, is returned as an issue so the gate fails and
  names the cause. The text fallback is still used when it actually
  recovers findings, which is what keeps pyscn's text output reporting its
  one real finding instead of cobra help text.
- **`crackerjack/models/tool_config.py`** — `PYSCN_MAX_COMPLEXITY = 25`,
  the single source for the threshold the parser and the adapter's
  `--max-complexity` flag share.
- **`crackerjack/adapters/sast/pyscn.py`**, **`crackerjack/cli/clone_cli.py`**
  — both resolve pyscn through the version-aware resolver.
- **`.pyscn.toml`** — the `cbo.enabled` key is removed; pyscn >= 1.30
  rejects it, even though its own `pyscn init` template still writes it.

## Transitions

| From | To | Date | Trigger | Evidence |
|------|----|------|---------|----------|
| (none) | `draft` | 2026-11-07 | Entry created | — |
| `draft` | `wired` | 2026-11-07 | The pyscn hook resolved `/usr/local/bin/pyscn` 1.33.0 over a stale 1.5.0 earlier on `PATH`, and the snake_case report it produced was parsed end-to-end by the gate | `crackerjack run -v -t` on `feat/pyscn-ruff-integration` |

## Links

- **Plan:** `docs/plans/2026-11-07-pyscn-intel-marker-and-json-schema.md`
- **Canonical doc:** none
- **Issue / discussion:** none — Bodai repos track work in `docs/plans/`,
  not the issue tracker.
- **Related entries:** none

## Rollback signal

`git revert` the merge commit on `main`. That restores the
`pyscn==1.5.0` pin, the CamelCase parser, and the text-parser fallback
together. There is no runtime flag: the pyscn version requirement is
compile-time in the dependency marker and in the parser, so turning it off
needs a code change.

## Observability

- The resolver's choice is visible in the gate log: the `pyscn` hook's
  resolved command line names the absolute binary it ran.
- `crackerjack run -v -t` reports the pyscn hook's issue count; a report
  that cannot be parsed appears as `pyscn report could not be parsed: ...`
  rather than as a silent zero.
- The complexity metric itself moved between pyscn versions (13 under 1.5.0,
  23 under 1.33.0 for the same function), so the threshold is only
  meaningful relative to a pyscn version. `pyscn --version` and
  `PYSCN_MAX_COMPLEXITY` are the two numbers to compare.
