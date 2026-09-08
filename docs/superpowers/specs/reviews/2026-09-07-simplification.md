# Simplification Lens Review

> **Reviewer lens:** Simplification — "could this be simpler?" without domain bias.
> **Scope constraint:** User's scope decisions are pinned (hybrid CLI/Python, lifecycle + Swift hooks, lint + Jinja auto-format, Kotlin/Gradle in scope, CLI + MCP mirror). Focus is the *implementation approach within those constraints*, not the constraints themselves.

---

## Findings (most-severe first)

### F1 [HIGH] — 7 per-language MCP tools when 3 generic ones would suffice

The spec promises 7 new MCP tools (`run_swift_hooks`, `bump_swift_version`, `run_kotlin_hooks`, `bump_kotlin_version`, `check_web_lint`, `format_jinja_templates`, plus `detect_languages`). For v0.81 with 3 new languages, this 1-tool-per-language pattern doubles the MCP surface and triples the test surface, while providing no capability a generic tool wouldn't.

**Simpler:** 3 generic tools — `run_hooks(language: str, path: str)`, `bump_version(language: str, level: Literal["major","minor","patch"])`, `format_jinja(path: str)`. `detect_languages(path)` stays as-is.

**Trade-off accepted:** generic tools shift parameter-validation cost to the tool layer. That's a one-time cost vs. permanent 7-tool maintenance.

---

### F2 [HIGH] — Entry-point registry for v0.81 pays extensibility tax for zero beneficiaries

The spec defines `LanguageAdapter` as a `Protocol`, requires `adapters/base.py`, `adapters/registry.py`, and ships entry-point registration in `pyproject.toml`. None of this matters unless a third-party adapter ships in the same release. The "Rust/Go/Java/etc. support" item is explicitly deferred.

**Simpler:** ship adapters as in-process modules in `crackerjack/adapters/`. A single `ADAPTERS: list[LanguageAdapter] = [PythonAdapter(), SwiftAdapter(), ...]` constant. Promote to entry-point discovery in v0.82 when a Bodai repo actually needs a third-party adapter.

**Trade-off accepted:** v0.82 will need to migrate the registry shape, but that's a 1-day refactor vs. maintaining the Protocol/registry plumbing for 2-3 releases with no users.

---

### F3 [HIGH] — "Hybrid — external CLI primary, Python fallback" framing is misleading

The spec's headline says "hybrid" but the actual matrix is:
- **Swift**: external CLI only, no Python fallback exists or is planned
- **Kotlin**: external CLI only, no Python fallback
- **Web (stylelint/eslint/tsc/html-validate)**: external CLI only
- **Web (Jinja format)**: in-process Python, no external CLI exists
- **Python (existing hooks)**: external CLI primary, Python fallback

This is "external CLI by default, in-process only when no CLI exists" — not "hybrid with fallback". The spec language under-specifies when fallback runs (only when CLI is missing? when CLI fails?). The error-handling table does list "CLI not installed → skip hook with warning", which contradicts a "fallback" semantic (skip ≠ fallback).

**Simpler:** drop the "hybrid" framing. State per-hook whether it has an external CLI or is in-process. The `Hook.fallback` field on every hook is misleading; reserve it for hooks that actually have one.

---

### F4 [MEDIUM] — `Hook` dataclass over-models the common case

`Hook` carries 5 fields (`name`, `cli_command`, `fallback`, `timeout_seconds`, `autofix`). For Swift/Kotlin/Web-CLI hooks, `fallback=None`. For Python hooks that have a fallback, the fallback is the same shape every time (`ty → mypy → python -m mypy`). For Jinja format, `cli_command=()` and `fallback=jinja_format`.

**Simpler:** drop `fallback` from `Hook`. Make it a separate class for the few cases that need it (`PythonFallbackHook(Hook, fallback=...)`). Default `timeout_seconds=300` (5 min). The dataclass becomes `Hook(name, cli_command, *, autofix=False, timeout_seconds=300)`.

---

### F5 [MEDIUM] — Jinja canonical policy of 7 rules is excessive for v1

The 7 rules are: spacing inside delimiters, blank line between top-level blocks, preserve existing blank lines, trailing newline, no trailing whitespace, inline vs. block policy, and trim-only-when-source-trims.

Rules 2, 3, and 6 interact (where do you put a blank line if you preserve existing ones, but only at the top level?). Rule 7 is a non-modification rule (don't introduce new trimming) — encoding "do nothing new" as a canonical rule is noise.

**Simpler:** 4 rules for v1 — single-space inside delimiters, trailing newline, no trailing whitespace, blank line between top-level `{% block %}` tags. Defer rules 3, 6, 7 until a contributor files a request. Each rule has tests; halving rule count halves test matrix.

---

### F6 [MEDIUM] — Cross-package Jinja parity test corpus is YAGNI for v1

The spec says parity is verified "manually + via a documentation note" on the Kotlin side because "we can't invoke PyCharm from headless CI". If CI can't verify parity, the corpus is documentation dressed as tests. The 30-input corpus adds maintenance without enforcement.

**Simpler:** delete "Cross-package parity tests (Jinja)" section from v0.81 spec. The crackerjack-side formatter still needs its own round-trip tests (`format(parse(format(x))) == format(x)`), which is a 1-package concern. Re-introduce parity corpus when IntelliJ CLI test framework becomes real.

---

### F7 [MEDIUM] — Phase 5 "Polish" doesn't earn its phase

Phase 5 is three items: registry column update, README update, parity test corpus. The registry column update and README update should happen *with* each phase that introduces new languages (Swift lands in Phase 2 → registry updates in Phase 2). Parity corpus is F6.

**Simpler:** drop Phase 5 as a separate phase. Fold documentation/registry updates into each prior phase as "Integration Contract" deliverables (matches the wire-up-contract discipline).

---

### F8 [LOW] — Web detection lists 10 file extensions + 4 directory globs without opt-in

Detection logic: `.css, .scss, .html, .ts, .tsx, .js, .jsx, .jinja, .html.j2, .tmpl` in `src/templates/`, `templates/`, `assets/`, `static/`. A Python project with a stray `.html.j2` in `static/` (e.g., a static page that nobody touches) gets the Web adapter enabled, then fails because `npx stylelint` isn't installed.

**Simpler:** require opt-in for Web adapter via `[tool.crackerjack.languages.web] = true` in `pyproject.toml`. Detection only kicks in when the user opts in. This avoids false-positive gate failures on legacy Python projects.

---

### F9 [LOW] — Hidden complexity: which adapter's lifecycle wins when both Python and Web are detected?

The spec says "Lifecycle runs only for Python (Web has no lifecycle)" for a fastblocks-style project. But the Web adapter's `Lifecycle` returns `None` per the contract — which is the rule? If Web's lifecycle is None and Python's is not, the spec is correct but should state it. If Web ever gets a lifecycle (CSS/HTML/JS/TS are explicitly out of scope per spec), the precedence rule needs to be explicit.

**Simpler:** add a one-line rule to the spec: "When multiple lifecycle-capable adapters are detected, run the first one in `ADAPTERS` declaration order and skip the rest, surfacing a warning."

---

### F10 [LOW] — `VersionSource.write()` read-back verification is expensive and not specified

The spec says "SwiftPM doesn't have a structured parser ... so we use regex with verification (read back after write, fail if mismatch)". This is fine for Swift, but the spec doesn't say whether Kotlin's `gradle.properties` rewrite also reads back. Reading `Package.swift` twice is cheap; rewriting `gradle.properties` and parsing it again is also fine, but should be uniform.

**Simpler:** mandate round-trip verification on every `VersionSource.write()` and add a `VersionSourceContract` test that runs once per adapter. The cost is one test file; the gain is uniform data-integrity guarantees.

---

## Coverage Statement

I reviewed:
- The full spec (lines 1–381)
- The user's pinned scope decisions (excluded from second-guessing)
- The implementation approach within those constraints

The most impactful simplifications are **F1** (collapse 7 MCP tools to 3 generic ones), **F2** (skip entry-point registry for v0.81), and **F3** (drop misleading "hybrid" framing). Together, these three changes would reduce the MCP surface by 50%, defer the registry complexity by one release, and clarify the actual implementation matrix. The other findings are smaller wins but compound: F4+F5+F6+F7+F8 together would remove roughly 30–40% of the v0.81 test surface while preserving all stated capabilities.

No findings question the user's chosen scope (Swift + Kotlin + Web + Jinja + lifecycle + lint + MCP mirror). All findings target the *shape* of the implementation within that scope.

**Status: REVIEW_COMPLETE**
