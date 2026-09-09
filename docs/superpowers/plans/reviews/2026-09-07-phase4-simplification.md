# Simplification Lens Review — Phase 4 (Web / CSS / HTML / JS / TS + Jinja)

**Phase 4 plan:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase4.md` (Tasks 1-7, 7 commits, ~1437 lines).
**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2). Phase 4 at spec lines 363-429 + 703-714.
**Precedent:** `/Users/les/Projects/crackerjack/docs/superpowers/plans/reviews/2026-09-07-phase3-simplification.md`.

**Focus:** implementation-level over-engineering, YAGNI within the user's stated scope (Web hooks + Jinja formatter + 2 MCP tools). Scope choices themselves are not second-guessed.

**Method note:** unlike the Phase 3 review, several findings here are **empirically verified** against the repo's own `jinja2 3.1.6`, `pyproject.toml`, and installed toolchain rather than reasoned from the plan text. Verified claims are marked *(verified)*. Three of them invalidate the plan's own "Expected: N passed" gates.

---

## Findings (most-severe first)

### F1. BLOCKER — Tier 2 `_normalize_one_space_inside_delimiters` deletes template content, and fails its own test

**Task 4, Step 4.** The regex:

```python
pattern = re.escape(open_d) + r"(\S)(.*?)(\S)" + re.escape(close_d)
def repl(m: re.Match[str]) -> str:
    return f"{open_d} {m.group(2)} {close_d}"
out = re.sub(pattern, repl, out, flags=re.DOTALL)
```

`repl` returns **only `group(2)`**. Groups 1 and 3 — the first and last non-whitespace characters, captured by the two `(\S)` — are discarded. Running the plan's exact implementation *(verified)*:

| Input | Plan's output |
|---|---|
| `{%if x%}A{%endif%}` | `{% f  %}A{% ndi %}` |
| `{{var}}` | `{{ a }}` |
| `{#note#}` | `{# ot #}` |
| `{% if x %}A{% endif %}` | `{% if x %}A{% endif %}` (no match) |

Two consequences:

1. **The plan's own test fails.** `test_tier2_when_normalize_true` asserts `"{% if x %}" in result` for input `{%if x%}A{%endif%}`. Actual result is `{% f  %}A{% ndi %}` *(verified: assertion is `False`)*. **Task 4 Step 5's "Expected: 9 passed" is unachievable as written.**
2. **The rule never fires on the inputs it's for.** `(\S)` cannot match the space immediately after `{%`, so already-spaced tags never match — including `{%  if x  %}` (double space), which is precisely what "exactly one space inside delimiters" exists to fix. The only inputs the regex touches are the ones it corrupts.

**Answer to review Q11 ("is the regex simple enough?"):** it is not too simple — it is *too clever and wrong*. `re.escape` + non-greedy + `DOTALL` + a closure + three delimiter pairs is four abstractions solving a problem the plan has already paid for a better tool to solve.

**Simplification.** `format_template` already holds the token stream. Tier 2 on tokens is a straight walk with no regex, no escaping, and no delimiter-specific branching:

```python
# for each begin…end run: emit begin + " " + " ".join(inner_values.split()) + " " + end
```

Delete the regex, the `re` import, the `DOTALL`, and the nested `repl`. It is fewer lines, correct for custom delimiters for free, and cannot lose characters.

**Severity:** Blocker. Data-destroying on the opt-in path, and the plan's stated verification gate cannot pass.

---

### F2. BLOCKER — `"".join(value for _, _, value in tokens)` is not a lossless reconstruction; it replays whitespace stripping into the source

**Task 4, Step 4.** The plan calls this "the canonical form for Tier 1". It is not source-preserving. jinja2's lexer folds stripped whitespace *into the token values* — e.g. `(1, 'block_end', '-%} ')` *(verified)* — so joining the values replays the strip against the file text.

Against the plan's **own fixtures** *(verified)*:

| Case | Original | Rejoined |
|---|---|---|
| `whitespace.html` fixture (Task 7) | `'{%- if x -%}\n  A\n{%- endif -%}\n'` | `'{%- if x -%}\n  A{%- endif -%}'` |
| Indented `{%-` (common Jinja style) | `'<div>\n  {%- if x %}\n    <p>hi</p>\n  {%- endif %}\n</div>\n'` | `'<div>{%- if x %}\n    <p>hi</p>{%- endif %}\n</div>'` |

The newline before `{%- endif` is deleted; all indentation before `{%-` tags is destroyed. Rendered output is unchanged (that whitespace was going to be stripped at render time anyway) — but a *formatter* that silently rewrites the author's source layout on first contact is worse than one that does nothing. Tier 1's stated contract is "preserve `{%-` / `-%}` / `{{-` / `-}}` markers"; the markers survive, the surrounding source does not.

**Why the test suite is green anyway.** The loss happens on pass 1; pass 2 is stable. So `format_template(format_template(x)) == format_template(x)` **passes** while pass 1 mangled the file. Spec line 412 called this out in advance — "*not just 'idempotence' which is weaker than it looks*" — and mandated golden-master expected output for exactly this reason. The plan's `test_round_trip_invariant` uses a source with no `{%-` markers, so it never reaches the lossy path; `test_format_preserves_whitespace_control_markers` only substring-checks `"{%- if x -%}"`, which survives while its neighbours don't. See F9: no golden-master test exists.

**Simplification (this one *removes* the feature, not adds to it).** Tier 1 as specified — trailing newline at EOF, no trailing whitespace per line, preserve markers — is **two line-level string operations and requires no lexing at all.** Use `env.lex()` purely as a *validation gate* ("does this file lex? if not, skip it and report"), then apply the two Tier 1 edits to the **raw source**. That deletes the reconstruction step, the entire class of whitespace loss, and the need to reason about lexer token semantics. It is strictly less code than what the plan has.

Related: the plan's `if not fixed.endswith("\n"): fixed += "\n"` is silently doubling as lexer-artifact repair. The default lexer turns `'A\n'` into `'A'` *(verified)*; `jinja2.Environment(keep_trailing_newline=True)` preserves it *(verified)*. Right now a formatting rule and a lexer quirk cancel out — a coincidence that breaks the day someone reorders the fix-ups.

**Severity:** Blocker. Silent source mutation on the always-on tier, with a test suite structurally unable to detect it.

---

### F3. BLOCKER — Task 6's four MCP tests will error under `asyncio_mode = "auto"`

`pyproject.toml` sets `asyncio_mode = "auto"` *(verified)*. The plan's new tests are `async def test_*` **and** call `asyncio.run(...)` in the body:

```python
async def test_check_web_lint_returns_three_hook_names(tmp_path: Path) -> None:
    ...
    _, tools = asyncio.run(_register())
```

Under auto mode pytest-asyncio runs the coroutine, so the inner call raises `RuntimeError: asyncio.run() cannot be called from a running event loop` *(verified)*. All four tests error, not fail. **Task 6 Step 4's "Expected: 17 passed" is unachievable.**

The existing 13 tests in the same file are sync `def test_*` with an inner `asyncio.run(...)` — correct, and the shape the plan should have copied *(verified: 13 tests collect and the file's precedent is unambiguous)*.

**Simplification:** drop the `async` keyword (or drop the inner `asyncio.run` and `await` directly). Additionally, the plan introduces

```python
monkeypatch = pytest.MonkeyPatch()
try:
    monkeypatch.setenv(...)
    ...
finally:
    monkeypatch.undo()
```

where the file already uses `with mock.patch.dict(os.environ, {...}, clear=True):` — one line instead of five, and `clear=True` actually isolates ambient env vars, which `delenv` does not. Match the file.

**Severity:** Blocker on execution. Trivial to fix; would waste an implementer's cycle diagnosing it.

---

### F4. HIGH — the `;` separator in `web.eslint_tsc`'s argv is not executable; Task 3 ships a command no runner can run

**Task 3, Step 5.** `_eslt_hook` emits argv tuples containing a literal `";"`:

```python
cmd = _npx_command("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx") + (";", "tsc", "--noEmit")
```

`Hook.cli_command` is contractually "argv list, no shell" (spec API F6; the plan's own Global Constraints line 30). `run_hook_with_fallback` does `subprocess.run(list(hook.cli_command), ...)` with no `shell=True`. So `";"`, `"tsc"`, `"--noEmit"` are passed **as literal arguments to eslint**, which will attempt to lint files named `;` and `tsc`. `tsc --noEmit` never executes.

The plan's own comment admits no such runner exists:

> "the `cli_command` encodes the eslint invocation, and tsc is appended by the runner as a follow-up. For the brief, we encode the combined command as a shell-style argv that the runner treats as sequential."

No runner treats it as sequential. This is **Phase 3 review F1 repeated verbatim** — an API shape implying behavior that nothing implements, with an in-code comment acknowledging the gap.

**Answer to review Q7 ("combined hook or separate?"): separate hooks.** `Hook` is one-argv-one-hook by construction; `web.eslint` + `web.tsc` need zero new machinery and are strictly simpler:

- No `;` fiction, no hypothetical sequential runner.
- Independent timeouts (300 each) instead of a fused 600 that hides which half was slow.
- Independent pass/fail, so a report says *which* tool failed.
- A JS-only project (no `typescript` in `devDependencies`) drops `web.tsc` naturally — the same skip-with-warning shape Kotlin already uses in `_build_hooks`.
- `_eslt_hook`'s three-way branch collapses to two one-line factories.

Two latent defects are visible only because the hook is fused, and both disappear with the split: the `elif eslint_pinned:` branch silently drops `--ext`, and the `else:` branch npx-prefixes eslint but leaves `tsc` bare.

**Severity:** High. A shipped hook that cannot run its second half, with the gap documented rather than fixed.

---

### F5. HIGH — the hybrid guard is inverted: the fallback fires when the tool *is* installed, and never when it isn't

**Task 3, Step 5.** The guard:

```python
cli_name = hook.cli_command[0]
if cli_name != "npx" and shutil.which(cli_name) is None:
    ...invoke fallback...
```

Both branches are wrong for the way the hooks are actually built *(all verified on this machine)*:

- **Unpinned (the default path).** `cli_command[0] == "npx"` → the guard's `!= "npx"` clause exempts it → **the fallback is unreachable**, even with nothing installed. `shutil.which("npx")` is `/usr/local/bin/npx`, so all three hooks always take the CLI path.
- **Pinned.** `cli_command[0] == "stylelint"` — but pinned tools live in `node_modules/.bin`, not on `PATH`. `shutil.which("stylelint")` is `None` *(verified)* → **the fallback fires despite the tool being correctly installed**, and the real linter is never run.

Compounding it: on the CLI path `run_hook_with_fallback` ends with

```python
if result.returncode != 0:
    logger.warning(...)
return []
```

— `return []` unconditionally, with the comment "CLI parsing is a Phase 4.5 concern". So the *primary* path of all three hooks reports zero issues, always. Unpinned + npx + `return []` = **three hooks that are green by construction**, which is the "MCP surface health illusion" failure mode the project already has a memory and a decision doc about (`.claude/decisions/mcp-backend-wiring-discipline.md`: "every registered tool must have a working data feed").

**Answer to review Q4 ("is 3 hooks + 3 fallbacks the minimum?"): no — it is above the minimum and below working.** The minimum honest shape is one resolver:

```python
def _resolve(project_root: Path, tool: str) -> tuple[str, ...] | None:
    # node_modules/.bin/<tool>  ->  PATH  ->  npx (if npx exists)  ->  None
```

One function replaces `_npx_command`, `_has_pinned_version`, the three per-hook pinned/unpinned branches, **and** the inverted guard — and it resolves correctly in all four cases. Then either raise with install instructions (`cli_required=True`, `fallback=None` — the Swift/Kotlin precedent) or call a fallback, with no `!= "npx"` special case anywhere.

**Severity:** High. The hybrid pattern is the phase's central mechanism and it is non-functional in both directions.

---

### F6. HIGH — the three Python fallbacks are ~90 LOC that cannot fail on any of the plan's own fixtures, and two of them are the same function

**Task 3, Step 4.**

**They are duplicates.** `css_fallback` and `js_ts_fallback` have byte-identical brace-counting bodies; `css_fallback` appends one empty-rule regex. That is the Rule of Three violation Phase 3 review F6 flagged for `git_backend.py` — except here both copies are being written *in the same commit*, so the "two copies is coincidence" defence doesn't apply.

**They are lexer-naive.** Both count braces in raw text, so braces inside CSS strings (`content: "{"`), JS template literals, regex literals, and comments all miscount. `const s = "{"` yields a false `"Unclosed brace(s) at EOF"`. A linter fallback whose failure mode is false positives on valid code is worse than absent.

**`html_fallback` (33 LOC) returns `[]` for every fixture in the plan** *(verified)*:

| Input | Result |
|---|---|
| `web-vanilla/src/index.html` (`<!DOCTYPE html>\n<html><body><h1>Hello</h1></body></html>\n`) | `[]` |
| the test's `<html><body></body></html>\n` | `[]` |
| `<div class="a"><p>x</p></div>` | `[]` |
| `<script>if (a < b) {}</script>` | `[]` |
| `<div><p>x</div>` (genuinely broken) | 3 issues |

It fires only on gross tag imbalance. `<DIV></div>` false-positives on case.

**The tests don't test them.** All three fallback tests assert only `isinstance(issues, list)`. They pass against `def css_fallback(p): return []`.

**Answer to review Q5 ("too simple? too complex?"): both, simultaneously.** Too crude to catch anything a developer would care about; too intricate (hand-rolled scanners with per-character line-number bookkeeping, a void-element table, comment skipping) for what they deliver. Given F5 makes them unreachable in the default configuration, the two honest options are:

1. **Delete all three.** Set `cli_required=True`, `fallback=None`, and fail with install instructions — exactly the Swift and Kotlin precedent, and exactly the call Phase 3 review F8 blessed ("The plan correctly does NOT add `fallback` callbacks. This is YAGNI-correct."). Removes ~90 LOC, 3 tests, a whole module, and the inverted guard.
2. If a fallback is genuinely wanted, ship **one** function — `_brace_balance(path)` shared by CSS and JS — and drop HTML.

Option 1 is the recommendation. Note that choosing it means Phase 4 has **no hybrid hooks**, which resolves spec Testing F3's mandatory two-path pair the same way Phase 3 did, and should be stated explicitly in the plan (Phase 3 review F8's under-documentation complaint).

Also: `except (OSError, UnicodeDecodeError): return []` in all three fallbacks swallows the error with **no logging at all** — a silent failure, and a miss against the plan's own Global Constraint line 28 (`logger.exception(...)` in `except` blocks).

**Severity:** High. ~90 LOC of duplicated, unreachable, untested heuristics.

---

### F7. MEDIUM — `test_web_hooks_invokes_python_fallback_when_cli_missing` asserts `[] == []`

**Task 3, Step 2.**

```python
with mock.patch.object(
    __import__("crackerjack.adapters.web.hooks", fromlist=["run_hook_with_fallback"]),
    "run_hook_with_fallback",
) as mock_run:
    mock_run.return_value = []
    hooks = web_hooks(tmp_path)
    for hook in hooks:
        result = mock_run.return_value  # smoke call
        assert result == []
```

It patches the function, never calls it, then reads back the value it just assigned. It passes if `run_hook_with_fallback` is deleted entirely. The `__import__(..., fromlist=[...])` gymnastics is a plain `import crackerjack.adapters.web.hooks as mod`.

This is the **single test** standing in for spec Testing F3's *mandatory* hybrid two-path pair — the one test that would have caught F5. Exact repeat of Phase 3 review F5.

Two more fake-greens in the same family:

- `test_tier1_only_when_normalize_false`: `assert "{%if x%}" in result or "{% if x %}" not in result`. The right-hand clause is true regardless of what the code does, so the `or` makes the assertion unfalsifiable.
- `test_capabilities_exposes_jinja_formatter_factory`: asserts `caps is not None`, with a four-line comment explaining that it does not test what its name says. Delete it; the name is a promise the body doesn't keep.

**Simplification:** replace all three with the two tests that matter — a CLI-present/CLI-missing pair against the resolver from F5, and one golden-master assertion from F9.

**Severity:** Medium. Test count without coverage; directly responsible for F5 shipping undetected.

---

### F8. MEDIUM — the MCP tool cannot reach custom delimiters; Phase 4's headline capability is built but not wired

**Task 6, Step 3.**

```python
formatted = await asyncio.to_thread(format_template, path.read_text())
```

No `delimiters`, no `normalize`. `_env()` therefore always uses standard `{%` / `{{` / `{#`.

- **fastblocks** — the named Phase 4 test target (spec line 713) and the whole motivation for the 6-delimiter work (spec line 396: "fastblocks sets all 6 … Source of truth") — uses `[%` / `[[` / `[#`. The MCP tool cannot format it.
- Spec Data Flow line 576 specifies the config source: `pyproject.toml` `[tool.crackerjack.jinja]`, all 6 keys. **Nothing in the plan reads that block.** The plan's Global Constraint line 47 also names `[tool.crackerjack.jinja] normalize = true` as the Tier 2 gate; nothing reads that either.
- So `DEFAULT_DELIMITERS`, the `delimiters` parameter, and the `normalize` parameter exist **only for tests**. Six delimiter kwargs are plumbed to a call site that never varies them.

This is the "built but not wired" state CLAUDE.md's Process Discipline section and `.claude/decisions/wire-up-contract.md` exist to prevent; `scripts/audit_orphans.py` is the named check.

**Simplification (again, *less* code than the status quo).** One reader:

```python
def _jinja_config(project_root: Path) -> tuple[Mapping[str, str], bool]:
    """Return (delimiters, normalize) from [tool.crackerjack.jinja], defaulted."""
```

called once per project dir and passed to both params. That is strictly smaller than shipping a parameter surface no caller exercises, and it makes the 6-delimiter constraint load-bearing instead of decorative.

Two smaller notes on the same tool:

- It writes unconditionally (`path.write_text(formatted)`) even when the content is unchanged — no diff, no change count, and **no `dry_run`**, where the sibling mutation tool `kotlin_bump_version` has one. Spec Data Flow line 580 asks for "per-file diff and exit code".
- The plan wraps only `format_template` in `to_thread` but leaves `read_text()` / `write_text()` on the event loop, so the sync I/O it was offloading is partly back. Wrapping the whole read-format-write unit in one `to_thread` is fewer thread hops *and* actually satisfies Global Constraint line 29.

**Severity:** Medium (structurally High if fastblocks is a Phase 4 acceptance target — spec line 713 says it is).

---

### F9. MEDIUM — the three golden-master Jinja fixtures are orphans; no test opens them

**Task 7, Step 1** creates `basic.html`, `custom_delimiters.html`, `whitespace.html` and labels them "Golden-master test inputs" (File Structure, plan line 87). **No test in Task 4, 6, or 7 reads them.** `test_web_vanilla_fixture.py` checks only `package.json` presence and adapter detection.

There are also no `*.expected` files, so there is no golden *master* — only inputs. The plan's Global Constraint line 46 requires "Test with golden-master expected output"; spec line 412 makes golden-master the entire point, because idempotence alone is "weaker than it looks". F2 is precisely the bug golden-master would have caught, on precisely the `whitespace.html` fixture the plan created and then didn't use.

Two structural notes:

- **`custom_delimiters.html` wouldn't exercise custom delimiters even if wired.** It mixes `{# … #}`-style comments with `[% … %]` tags. Under a custom-delimiter `Environment` the first line lexes as data *(verified — no `TemplateSyntaxError`)*, so the file tests neither delimiter set cleanly.
- **The nesting is wrong.** `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/` puts a `tests/fixtures/` inside a fixture inside `tests/fixtures/`. Jinja templates are not part of the `web-vanilla` npm project. `tests/fixtures/jinja-templates/` alongside `web-vanilla/` matches the existing flat convention *(verified: `tests/fixtures/` currently holds `swift-lib/`, `gradle-vanilla/`, `full/`)*.

**Simplification:** either add the ~10-line golden-master test (`for f in dir.glob("*.html"): assert format_template(f.read_text(), …) == f.with_suffix(".expected").read_text()`) — which is the cheapest possible defence against F1 and F2 — or delete the three fixtures. Shipping unused fixtures labelled "golden-master" is worse than either, because it reads as covered.

**Severity:** Medium. Phase 3 review F1's orphan pattern, applied to the fixtures that would have caught this phase's two blockers.

---

### F10. MEDIUM — `detection.py` diverges from the Swift/Kotlin precedent for ~15 lines, and a third of it is dead code on Python 3.14

**Task 2, Step 3.**

**Answer to review Q6 ("`package_json_present()` + `web_enabled()` — premature abstraction?"):** the two-function split is not harmful in itself. The **module** is the divergence. `SwiftAdapter.detect()` inlines `(project_root / "Package.swift").is_file()`; `KotlinAdapter.detect()` inlines the two `build.gradle` checks. Neither ships a detection module *(verified: `swift/` = `__init__, git_backend, hooks, lifecycle, platforms, version_source`; `kotlin/` = `__init__, git_backend, hooks, lifecycle, version_source`)*. Phase 4 is the only adapter with `detection.py`, for two functions.

**Dead code inside it.** `requires-python = ">=3.14"` *(verified)*, so `tomllib` is always importable. This can never take its second branch:

```python
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        return False
```

Six lines, a nested `try`, and a `# type: ignore` for a Python 3.10 path the project cannot run on. It is also an inline import for a stdlib module with no cycle risk, against the plan's own Global Constraint line 31.

**Simplification:** fold into `web/__init__.py`, hoist `import tomllib` to module scope, delete the fallback ladder. `web_enabled` becomes ~12 lines with a flat `try/except tomllib.TOMLDecodeError`. Net: −1 module, −1 function, −2 tests, −6 lines of unreachable imports — and Phase 4 stops being the odd adapter out. Keep `package_json_present` only if something outside `web_enabled` calls it; today nothing does.

**Severity:** Medium. Structural divergence plus guaranteed-dead code, both cheap to remove.

---

### F11. LOW — CF-2 is correctly followed; the "lazily built formatter" claim has no referent

**Answer to review Q10: yes, the plan follows Phase 2 CF-2.** `WebAdapter.capabilities()` constructs no formatter and no lifecycle:

```python
return Capabilities(version_source=None, hooks=web_hooks(project_root), has_lifecycle=False)
```

It also avoids Phase 3's `_ = make_git_backend` lint-silencing smell (Phase 3 review F3) — no dead import, no post-hoc justification comment. Credit where due: this is the cleanest `capabilities()` of the three new adapters.

Two cosmetic notes:

- Task 5's header says the formatter "is lazily built by the MCP handler (Task 6)", and the test comment repeats it. There is no formatter *object* — `format_template` is a module-level function. "Lazily built" describes a factory that doesn't exist and invites a future reader to look for one. One sentence: "Phase 4 has no formatter object; `Capabilities` gains no new field."
- `version_source=None` is passed explicitly with a comment; the dataclass already defaults it. Harmless either way — keep for symmetry with Swift/Kotlin, which pass real sources.

**Severity:** None on the code. Trivial on the prose.

---

### F12. LOW — `_env()` is acceptable; add `keep_trailing_newline=True`

**Answer to review Q8: yes, acceptable — keep it.** It is the single place the 6-kwarg requirement (Global Constraint line 45 / spec Jinja F2) is enforced, and naming it makes that auditable in one grep. A single-purpose helper that pins a spec constraint is worth its four lines.

Two changes:

1. **Add `keep_trailing_newline=True`.** It is the documented lexer caveat (spec line 377) and *(verified)* it is the difference between `'A\n' → 'A'` and `'A\n' → 'A\n'`. Today Tier 1's "add trailing newline" rule and this lexer artifact happen to cancel out; make the behavior intentional. (Moot if F2's recommendation lands and Tier 1 stops going through the token stream — but then `_env()` is purely a validation gate and the flag still belongs there.)
2. **Don't `KeyError` on a partial config.** `delimiters["block_start"]` against a 5-key `[tool.crackerjack.jinja]` block gives a bare `KeyError` with no indication which key or which file. One `_REQUIRED_KEYS - delims.keys()` guard raising a named error, or an explicit docstring line that callers must pass complete dicts. Relevant the moment F8's config reader exists.

**Severity:** Low.

---

### F13. LOW — magic strings: two worth hoisting, the rest fine inline

**Answer to review Q9.**

Worth hoisting:

- **`{".html", ".j2", ".jinja"}`** (Task 6, Step 3) is the only *policy* string in the phase — it decides which files get overwritten. Hoist to `jinja_formatter.JINJA_SUFFIXES` next to `DEFAULT_DELIMITERS`, so the formatter owns its own file-type policy and the MCP tool doesn't encode it. `.html` also deserves scrutiny: it runs plain HTML through a Jinja lexer, and the plan's own `web-vanilla/src/index.html` is not a template. A `{{` inside a JS template literal in a plain `.html` file is a lex failure at best.
- **`_FALLBACK_ISSUE = tuple[Path, int, str]`** is a type alias in SCREAMING_CASE assigned without `TypeAlias`. On 3.14: `type FallbackIssue = tuple[Path, int, str]`. (Moot if F6 lands.)

Fine as-is:

- Hook names (`"web.stylelint"`, `"web.eslint_tsc"`, `"web.html_validate"`), `"npx"`, `"--no-install"`, `"**/*.css"`. Swift and Kotlin inline the same kind of literal; adding constants would be noise.
- `VOID_ELEMENTS` is declared as a **local** inside `html_fallback` in SCREAMING_CASE and rebuilt on every call. `N806` is in the project's Ruff ignore list, so the gate won't catch it. Moot if F6 lands; otherwise module-level.

**Severity:** Low.

---

### F14. LOW — three of the plan's own "Expected: N passed" gates are wrong

These are the plan's verification checkpoints, so an implementer who hits a different number has to decide whether the plan or the code is at fault.

| Location | Plan says | Actual |
|---|---|---|
| Task 2, Step 4 | "8 passed" | the test file defines **9** tests |
| Task 6, Step 4 | "17 passed (existing 13 + 4 new)" | 13 existing *(verified)* → 17 ✓ **correct** |
| Task 7, Step 4 | "~80 passed (52 prior Phase 3 + 28 new Phase 4)" | the named paths collect **18** today *(verified)*, and the plan's new files add **41** (9+8+9+8+3+4) → ≈ **59** |

Task 6 and Task 4 gates are separately unachievable for the reasons in F3 and F1.

**Severity:** Low, but it compounds F1/F3 — an implementer will see multiple wrong counts and start ignoring the gates.

---

### F15. LOW — declaration order and inline imports in `hooks.py`

- **`WebHookError` is defined at the bottom of the module, after `run_hook_with_fallback` raises it.** Resolves fine at call time, but it reads as an accident and breaks the declare-before-use ordering every other module in `crackerjack/adapters/` follows. Move it to the top with the logger. Also: the test file imports it and never asserts on it — one `pytest.raises(WebHookError)` for the no-fallback path would earn the import.
- **`import json` inside `_has_pinned_version`** and `import tomllib` inside `web_enabled` (F10). Both are cheap stdlib with no cycle risk; module-level per Global Constraint line 31, matching Swift/Kotlin. Moot for `_has_pinned_version` if F5's resolver replaces it.
- **`logger.warning("Jinja lex failed: %s", exc)`** inside an `except` block in `format_template` — Global Constraint line 28 mandates `logger.exception(...)` in `except` blocks. One-word fix, and it's the plan's own rule.

**Severity:** Low.

---

## Review Q3 — Jinja formatter scope (spec says ~250-400 LOC)

**The plan's `jinja_formatter.py` is ~85 LOC — well under the spec's estimate. It is not over-engineered; it is under-built relative to its own stated policy.** The gap is exactly the unimplemented pieces:

| Required by | Item | In plan? |
|---|---|---|
| Spec line 576 / plan Global Constraint 47 | `[tool.crackerjack.jinja]` config reader (6 delimiters + `normalize`) | ✗ (F8) |
| Plan Global Constraint 47 | Tier 2 rule: blank line between block-level tags at top level | ✗ (listed, no code) |
| Plan Global Constraint 47 | Tier 2 rule: inline `{{ var }}` may remain inline | ✗ |
| Spec line 378 | CRLF preservation | ✗ |
| Plan Global Constraint 46 / spec 412 | Golden-master expected output | ✗ (F9) |
| Spec line 580 | Per-file diff + exit code | ✗ (F8) |
| Spec Data Flow 572 | `crackerjack web jinja format <path>` CLI subcommand | ✗ — and the plan's Tech Stack line 11 claims "typer 0.26+ for CLI surface" while no task adds a command |

**The simplifying move is to narrow the claim, not to add the missing pieces.** Ship **Tier 1 only** this phase: drop `normalize` from the signature, delete the two Tier 2 tests, and defer Tier 2 to a phase that can afford golden-masters. That lands ~60 LOC that provably works, and avoids shipping a `normalize=True` path that corrupts input (F1). Tier 1 is also the tier the spec marks "always on" and semantics-preserving — the one users get by default and therefore the one that must be right.

If Tier 2 must ship now, it needs the token-walk implementation (F1) *and* golden-master fixtures (F9). Regex + idempotence-only testing is not enough, as F1 and F2 both demonstrate.

---

## Review Q1 — YAGNI summary

Over-engineering is concentrated in exactly three places, all covered above:

1. The fused eslint+tsc argv with its imaginary sequential runner (F4).
2. Three hand-rolled, duplicated, unreachable Python fallbacks (F6).
3. The Tier 2 regex, where a token walk was already available and free (F1).

Everything else is appropriately scoped, and several scope *omissions* are correct:

- **No lifecycle** — correct per spec line 65, and `has_lifecycle=False` / `version_source=None` are asserted.
- **No `profiles.py` change** — correct; `language_tools` is already in `FULL_REGISTRATIONS` from Phase 2. The plan states this explicitly in "Files NOT modified", which is the right way to record a deliberate non-change.
- **No `server_core.py` change** — correct per Phase 2 BLOCKER B2.
- **No shared `jinja-test-fixtures/` package** — reasonable to defer.

One scope deferral needs a firmer home than a constraint bullet: Global Constraint line 48 defers PyCharm parity to "Phase 4.5", which does not exist as a plan. Spec Testing F4 makes parity a **Phase 4 acceptance criterion** and explicitly removes the documentation-note escape hatch ("The 'documentation note' fallback is **removed** — this is now a Phase 4 acceptance criterion"); spec line 420 makes the fixtures package a Phase 4 deliverable. Deferring both is defensible, but it is a spec amendment, and the plan's "Spec Revision Notes" section is empty. Record it there.

---

## Review Q2 — Pattern adherence

| Phase 3 pattern | Phase 4 | Verdict |
|---|---|---|
| Constructor injection (git-backend callables) | N/A — no lifecycle in Phase 4 | ✓ nothing to violate |
| `Module:ClassName` entry point | `web = "crackerjack.adapters.web:WebAdapter"` | ✓ *(verified: matches the 3 existing entries)* |
| 4-step MCP registration | Steps 2+3 correctly identified as already done; tools added to existing group; step 4 via tests | ✓ |
| Per-invocation auth on mutation tools | `_require_auth_config()` first statement in `format_jinja_templates`; `_validate_project_root` per path; reuses Phase 3's fail-closed helpers | ✓ |
| CF-2: `capabilities()` builds nothing heavy | No formatter, no lifecycle constructed | ✓ (F11) |
| CF-1: no dead defensive code | Avoids Phase 3's `_ = make_git_backend`, but adds the `tomli` ladder (F10) and the `;`-argv (F4) | ⚠ |
| Fake-green tests (Phase 3 F5) | Three instances | ✗ (F7) |
| Orphan API surface (Phase 3 F1) | `;` argv (F4), unused `delimiters`/`normalize` params (F8), unused fixtures (F9) | ✗ |
| Rule of Three (Phase 3 F6) | `css_fallback` ≡ `js_ts_fallback` in the same commit | ✗ (F6) |

Divergences from repo convention worth naming:

- **`detection.py`** — no other adapter has one (F10).
- **`async def` tests + inner `asyncio.run`** — the same file's 13 existing tests use sync `def` (F3).
- **`pytest.MonkeyPatch()` + try/finally** — the same file uses `mock.patch.dict(..., clear=True)` (F3).
- **No `dry_run` on the mutation tool** — `kotlin_bump_version` has one (F8).
- **Return-shape drift:** `check_web_lint` returns `{"adapter", "enabled", "hooks": [{...}]}` (a *list* of dicts) while `swift_list_hooks` and `kotlin_list_hooks` both return `dict[str, dict]` keyed by hook name *(verified in `language_tools.py`)*. Two shapes for one concept inside one tool group. Adopt the existing shape; the `adapter`/`enabled` keys are redundant with `detect_languages`.
- **Tool naming regression:** `check_web_lint` is a *listing* tool named `check_*`. Phase 2 deliberately renamed `swift_run_hooks` → `swift_list_hooks` with the rationale "this is a metadata tool that lists hook configs … It does NOT execute hooks" — still in the module docstring. `check_web_lint` reintroduces the naming that review corrected. The spec does name it `check_web_lint` (line 49), so `web_list_hooks` needs a Spec Revision Note rather than a silent change.

Finally, **Task 6 Step 5 is a manual step** ("Start the MCP server briefly and confirm …") where an automated equivalent already exists: `test_register_language_tools_registers_three_tools`. Extend that assertion instead — and note it must be renamed, since it will register **seven** tools after Phase 4 (`swift_bump_version`, `swift_list_hooks`, `detect_languages`, `kotlin_bump_version`, `kotlin_list_hooks`, plus the two new ones). The plan does not mention updating it, so Task 6 will break it.

---

## Coverage Statement

Reviewed the full Phase 4 plan (~1437 lines / 7 tasks / 7 commits) against all eleven focus areas:

1. **YAGNI** — covered. F1, F4, F6 are the three concentrations; scope *omissions* are mostly correct.
2. **Pattern adherence** — covered in the Q2 table. Entry point, 4-step MCP, and per-invocation auth all hold; CF-2 is the cleanest of the three adapters; test style, return shape, tool naming, and `detection.py` all drift.
3. **Jinja formatter scope** — covered in Q3. ~85 LOC vs spec's 250-400; under-built, not over-built; recommendation is to narrow the claim to Tier 1.
4. **Hybrid pattern complexity** — F5. Above minimum, below working; the guard is inverted in both directions.
5. **Python fallback simplicity** — F6. Both too crude and too intricate; recommend deletion per the Swift/Kotlin precedent.
6. **Detection guard split** — F10. The split is fine; the module is the divergence, and a third of it is dead on 3.14.
7. **CLI combined command** — F4. Should be two hooks; the `;` argv is not executable.
8. **`_env()` helper** — F12. Acceptable; add `keep_trailing_newline=True` and a completeness guard.
9. **Magic strings** — F13. Hoist `JINJA_SUFFIXES` and fix the type alias; the rest are fine inline.
10. **Phase 3 CF-2 carry-over** — F11. Followed correctly; only the "lazily built" prose needs a fix.
11. **Tier 2 normalization regex** — F1. Not too simple: wrong, and it fails its own test.

**Top 3 actions for the plan author:**

1. **F1 + F2 (both blockers, both in Task 4).** Replace the Tier 2 regex with a token walk, and stop using the token join as a source reconstruction. The smallest correct Task 4 is: `lex()` as a validation gate only, Tier 1 as two line-level string ops on raw source, Tier 2 deferred. That is *less* code than the plan and it does not mutate templates. Add the golden-master test from F9 against the `whitespace.html` fixture the plan already wrote — it is ~10 lines and it is what catches both bugs.
2. **F4 + F5 + F6 (Task 3).** Split `web.eslint_tsc` into `web.eslint` + `web.tsc`; replace `_npx_command` / `_has_pinned_version` / the inverted `which` guard with one `_resolve(project_root, tool)`; delete `python_fallbacks.py` and set `cli_required=True`, `fallback=None` per the Swift/Kotlin precedent. Then state explicitly, as Phase 3 review F8 asked, that Phase 4 hooks are non-hybrid so spec Testing F3's two-path pair is N/A. Net: −1 module, ~−120 LOC, and three hooks that fail honestly instead of passing vacuously.
3. **F3 + F8 (Task 6).** Make the four new tests sync `def` with `mock.patch.dict(..., clear=True)` to match the file, and update `test_register_language_tools_registers_three_tools` for the new count. Add the `_jinja_config()` reader so custom delimiters and `normalize` are reachable — without it the 6-delimiter constraint is decorative and fastblocks (the named Phase 4 target) cannot be formatted.

---

## Spec Coverage Summary

| Spec § Item | Plan Implementation | Verdict |
|---|---|---|
| Web hooks: stylelint / eslint+tsc / html-validate | 3 hooks emitted | ⚠ tsc unrunnable (F4); CLI path returns `[]` always (F5) |
| Hybrid pattern (CLI primary, Python fallback) | `run_hook_with_fallback` + 3 fallbacks | ✗ guard inverted both ways (F5) |
| Commands via `npx` unless `package.json` pins | `_npx_command` + `_has_pinned_version` | ⚠ pinned branch resolves to bare name not on PATH (F5) |
| Writing F3: detection guard (`package.json` OR opt-in) | `web_enabled()` | ✓ logic correct; module diverges (F10) |
| Jinja F1: `lex()` not `parse()` | `env.lex(source)` | ✓ chosen correctly; misused as a reconstructor (F2) |
| Jinja F1: preserve comments | comment tokens survive the join *(verified)* | ✓ |
| Jinja F1: tolerate unknown tags (`{% trans %}`) | *(verified: no raise)* | ✓ |
| Jinja F1 caveat: trailing newline restored from raw input | papered over by the Tier 1 fix-up, not by `keep_trailing_newline` | ⚠ (F12) |
| Jinja F1 caveat: CRLF → LF normalization | not handled | ✗ |
| Jinja F2: all 6 delimiter kwargs | `_env()` passes all 6 | ✓ but never varied by any caller (F8) |
| Jinja F3 Tier 1: trailing newline, no trailing whitespace, preserve markers | implemented | ⚠ markers preserved, surrounding source destroyed (F2) |
| Jinja F3 Tier 2: one space inside delimiters | regex | ✗ corrupts content; fails own test (F1) |
| Jinja F3 Tier 2: blank line between block-level tags | listed in constraints; no code | ✗ |
| Jinja F3 Tier 2: opt-in via `[tool.crackerjack.jinja] normalize` | `normalize` param; no config reader | ✗ (F8) |
| Jinja F11: `jinja2>=3.1.6` direct dep | Task 1 Step 3 | ✓ *(verified: currently undeclared)* |
| Jinja F10 / Testing F4: PyCharm one-way fixed point | deferred to "Phase 4.5" | ✗ spec makes it a Phase 4 acceptance criterion; needs a Spec Revision Note |
| Testing F9: round-trip invariant | `test_round_trip_invariant` | ⚠ passes while pass 1 is lossy (F2) |
| Testing F9: golden-master expected output | 3 input fixtures, no expected files, no test | ✗ (F9) |
| Testing F3: hybrid two-path test pair | one test asserting `[] == []` | ✗ (F7) |
| Testing F8: `tests/fixtures/web-only/` | `tests/fixtures/web-vanilla/` | ✓ name differs from spec, matches repo convention *(verified)*; nesting is wrong (F9) |
| MCP F1: 4-step registration | steps 2+3 already done; correctly not re-done | ✓ |
| MCP F5: auth on mutation tools | `_require_auth_config()` per invocation | ✓ |
| MCP F7: async/sync split | `asyncio.to_thread(format_template, …)` | ⚠ read/write left on the loop (F8) |
| MCP F2: rollback contract | N/A — no lifecycle | ✓ |
| Spec line 65: no CSS/HTML/JS/TS lifecycle | `has_lifecycle=False`, asserted | ✓ |
| Spec line 572: `crackerjack web jinja format` CLI | no task adds it, though Tech Stack claims a CLI surface | ✗ |
| Spec line 420: shared `jinja-test-fixtures/` package | explicitly out of scope | ✓ deliberate deferral |

---

## Plan Quality Verdict

**Request changes.** Phase 4 gets the *architecture* right — the detection guard is the correct shape, `capabilities()` is the cleanest of the three new adapters (no CF-2 regression, none of Phase 3's lint-silencing dead code), the 4-step MCP awareness is accurate, and per-invocation auth reuses Phase 3's fixed helpers rather than re-deriving them. Consolidating the spec's three hook files (`css_hooks.py` / `js_hooks.py` / `html_hooks.py`) into one `hooks.py` is a genuine simplification over the spec.

But the two central deliverables do not work as written, and I verified both against the repo's own `jinja2 3.1.6`:

- **The Jinja formatter's opt-in tier deletes characters** (`{%if x%}` → `{% f  %}`) and **its always-on tier deletes source whitespace** on the plan's own `whitespace.html` fixture. Both are invisible to the plan's test suite, because the round-trip invariant is stable *after* the lossy first pass and no golden-master test exists.
- **All three hooks are green by construction** — the npx exemption makes the fallback unreachable, and the CLI branch `return []`s unconditionally.

**3 BLOCKER (F1, F2, F3). 3 HIGH (F4, F5, F6). 4 MEDIUM (F7, F8, F9, F10).** Three of the plan's own "Expected: N passed" gates are unachievable (Task 2 count, Task 4 Tier 2, Task 6 asyncio) — the plan cannot be executed to green as written, so this is not a "fix during implementation" situation like Phase 3's.

The encouraging part: **every recommendation here removes code.** Token walk instead of regex (F1). Raw-source string ops instead of token reconstruction (F2). Two hooks instead of one fused hook with a fictional runner (F4). One resolver instead of four branching helpers (F5). Zero fallbacks instead of three duplicated scanners (F6). One config reader instead of three unused parameters (F8). Fold `detection.py` into `__init__.py` and drop the `tomli` ladder (F10). Estimated net: **−150 to −200 LOC** against the plan as drafted, with the two blockers resolved rather than worked around.

**Recommended next step:** revise Tasks 3, 4, and 6, then dispatch the remaining lenses of the multi-agent review (per Phase 2/3 process) against the revised plan. F1, F2, and F5 are correctness findings that surfaced under a simplification lens because the simpler implementation is also the correct one — a security or testing lens should confirm them independently before execution.

REVIEW_COMPLETE
