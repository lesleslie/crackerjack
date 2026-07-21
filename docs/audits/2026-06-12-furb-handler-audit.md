______________________________________________________________________

## status: complete role: historical date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# FURB_TRANSFORMATIONS Handler Audit — 2026-06-12

**Scope**: All 54 entries in `FURB_TRANSFORMATIONS` in `crackerjack/agents/refurb_agent.py`
**Method**: For each (code, handler) pair, construct a known-bad input, run the handler, compare output against the canonical "good" form from `refurb --explain <code>`.
**Driver**: `docs/audits/2026-06-12-furb-handler-audit-driver.py`
**Raw log**: `docs/audits/2026-06-12-furb-handler-audit-results.log`
**Refurb ground truth**: v2.3.1

## Headline

| Verdict | Count | % |
|---------|-------|---|
| CORRECT (handler does the right thing) | 9 | 17% |
| WRONG (handler produces wrong output) | 1 | 2% |
| NOOP (handler is a stub or wrong rule) | 44 | 81% |

**The dominant failure mode is wrong-handler-attached.** Most NOOPs map a code
to a handler that implements a *different* FURB rule. Same class of bug as
FURB183 (which we fixed in the prior commit).

## CORRECT (9)

| Code | Handler | Notes |
|------|---------|-------|
| FURB102 | `_transform_compare_zero` | `x == 0` → `not x`; `startswith('a') or startswith('b')` → tuple. Doc matches. |
| FURB105 | `_transform_print_empty_string` | `print("")` → `print()`. ✓ |
| FURB107 | `_transform_compare_empty` | AST path fires for `try/except: pass` → `with suppress(E)`. ✓ |
| FURB109 | `_transform_membership_test` | `in [a,b]` → `in (a,b)`. ✓ |
| FURB113 | `_transform_redundant_pass` | Correct for 2-append case. *(PARTIAL — see below)* |
| FURB115 | `_transform_open_mode_r` | `len(x) == 0` → `not x` matches doc. *(PARTIAL — destructive `len(x) >= 1` → `x` side branch.)* |
| FURB126 | `_transform_isinstance_type_check` | Removes trailing `else: return` blocks. ✓ |
| FURB145 | `_transform_copy` | `x[:]` → `x.copy()`. ✓ |
| FURB183 | `_transform_useless_fstring` | `f"{x}"` → `str(x)`. ✓ (prior bug fixed) |

## WRONG (1)

| Code | Handler | Problem | Fix |
|------|---------|---------|-----|
| FURB118 | `_transform_enumerate` | Emits `import operator` + `operator.itemgetter(N)`. Canonical form is `from operator import itemgetter; itemgetter(N)`. Verbose and fails pep8. | Switch to `from operator import itemgetter` import form. Trivial. |

## NOOP (44)

Grouped by failure pattern.

### Pattern A: Handler is a stub (1-line `return content, "..."` placeholder)

FURB108, FURB110, FURB111, FURB116, FURB119, FURB122, FURB125, FURB132, FURB133,
FURB134, FURB138, FURB140, FURB141, FURB142, FURB143, FURB148, FURB152, FURB156,
FURB157, FURB161, FURB163, FURB167, FURB168, FURB172, FURB173, FURB175, FURB176,
FURB177, FURB180, FURB181, FURB184, FURB185, FURB186, FURB187, FURB189, FURB190.

**Fix per code**: write the actual transform. See the suggested_fix column in
the raw log for AST sketches.

### Pattern B: Handler implements a different FURB rule than its mapped code

This is the most insidious category. The handler is real, the regex/AST works,
but the rule it implements is for a *different* FURB code. The mapping name
and the code name don't agree (likely a copy-paste error in the original
dict, frozen in by the lack of tests).

| Code | Mapped Handler | What the handler actually does | What FURB code should be |
|------|----------------|--------------------------------|--------------------------|
| FURB129 | `_transform_any_all` | Loops → `any()`/`all()` | FURB129 is `for line in f.readlines(): ...` → `for line in f: ...` |
| FURB131 | `_transform_single_item_membership` | `x in [y]` → `x == y` (FURB171) | FURB131 is `del nums[:]` / `nums[:] = []` → `nums.clear()` |
| FURB136 | `_transform_bool_return` | `if cond: return True` → `return bool(...)` (FURB127 area) | FURB136 is `h = a if a > b else b` → `h = max(a, b)` |
| FURB141 | `_transform_redundant_fstring` | Strips `f"{...}"` (FURB183) | FURB141 is `os.path.exists(p)` → `Path(p).exists()` |
| FURB142 | `_transform_unnecessary_listcomp` | `[x][0]` → `next(...)` | FURB142 is `for x in s: letters.discard(x)` → `letters.difference_update(s)` |
| FURB148 | `_transform_max_min` | Manual max/min loops | FURB148 is `for i, _ in enumerate(xs): print(i)` → `for i in range(len(xs))` |
| FURB152 | `_transform_pow_operator` | `math.pow(a,b)` → `a**b` | FURB152 is hardcoded `3.1415` → `math.pi` |
| FURB156 | `_transform_redundant_lambda` | `lambda x: f(x)` → `f` | FURB156 is `"0123456789"` → `string.digits` |
| FURB161 | `_transform_int_scientific` | `int("1.5e3")` → `1500` | FURB161 is `bin(x).count("1")` → `x.bit_count()` |
| FURB163 | `_transform_sorted_key_identity` | `sorted(x, key=lambda k: k)` → `sorted(x)` | FURB163 is `math.log(x, 10)` → `math.log10(x)` |
| FURB169 | `_transform_type_none_comparison` | `x == None` → `x is None` (FURB169-adjacent) | FURB169 is `type(x) is type(None)` → `x is None` (handler misses this) |
| FURB171 | `_transform_single_element_membership` | Looks for `[...]` square brackets, not `(...)` parens. Misses doc example `x in ("bob",)`. | Same code, broken regex. |
| FURB173 | `_transform_redundant_not` | `not (x == y)` → `x != y` | FURB173 is `{"a":1, **d}` → `{"a":1} | d` |
| FURB188 | `_transform_slice_copy` | Forwards to `_transform_copy` (`x[:]` → `x.copy()`) | FURB188 is `x[:-4] if x.endswith(".txt") else x` → `x.removesuffix(".txt")` |

**Fix**: for each row, either (a) write the actual transform the code documents, or
(b) change the mapping to point at a handler that does the right thing. The
audit log's `suggested_fix` column has an AST sketch for each.

### Pattern C: Real handler, too-narrow input match

| Code | Handler | Problem | Fix |
|------|---------|---------|-----|
| FURB113 | `_transform_redundant_pass` | Arg regex `[^\(\),\s\n]+` rejects string literals, dict args, dotted expressions. Also only chains 2 of N appends. | Drop the per-line state machine; use AST + `ast.unparse(arg)`. |
| FURB115 | `_transform_open_mode_r` | Has a destructive `len(x) >= 1` → `x` rewrite (silently drops the boolean). | Remove the `>= 1` branch. |
| FURB123 | `_transform_list_copy` | Regex `\blist\(([a-z_][a-z0-9_]*)\)` only matches `list(VAR)` with bare single word. Misses `list(some_obj)`, `str("x")`, `int(123)`, `dict(d)`. | Add `(str|int|float|bool|dict|list|set|tuple)\((.*?)\)` and AST-check the inner type. |
| FURB126 | `_transform_isinstance_type_check` | Regex `(\s*)else:\s*\n\s+return` matches any `else: return`, including broken indentation. | Restrict to `else` whose matching `if` already returns (use AST). |
| FURB138 | `_transform_list_comprehension` | Real AST rewriter, but the loop-detection walks miss the doc example. | Debug the AST walk; the doc example should be detectable. |

## Recommended order of attack

### Tier 1 — Quick wins (1-2 hours total, big impact)

- **FURB118**: change `import operator` → `from operator import itemgetter`. Trivial.
- **FURB115**: delete the destructive `len(x) >= 1` → `x` branch. Trivial.
- **FURB123**: generalize the regex to all redundant casts, not just `list(...)`. Small.
- **FURB113**: replace the state machine with AST. Small.
- **FURB126**: restrict the regex with AST. Small.

### Tier 2 — Wrong-rule redirects (4-6 hours, medium risk)

Fix the 14 Pattern B rows. Each is small (1 regex or 1 AST walk) but you
have to read `refurb --explain <code>` carefully to get the rule right.
Recommended: do them in numerical order (FURB129 first, then 131, 136, ...).
Each is independent.

### Tier 3 — Stub implementations (10-20 hours, the bulk of the work)

The 36 Pattern A stubs. Each is a one-rule transform. To go fast, generate
the AST-detection skeleton once and copy it for each rule, varying only
the predicate. See the `suggested_fix` column in the raw log for sketches.

### Skip for now

- Codes with names that strongly overlap existing handlers (FURB169 vs
  `_transform_type_none_comparison`) — leave the wrong-but-close mapping
  until the rest are done. The agent still won't make a *worse* fix than
  no fix, since `success=False` is returned on no-op.

## Meta-observations

1. **The dict was hand-built once and frozen.** There's no test pinning
   "this code maps to a handler that does the right thing." Without tests,
   copy-paste errors (like the FURB183 → `_transform_substring` mapping)
   became permanent. The new e2e test (`tests/test_agents/test_refurb_e2e.py`)
   catches the ghost-fix class of bug; the audit log catches the
   wrong-handler class.

1. **The fixer layer (refurb_fixer.py) is healthier than the agent layer
   (refurb_agent.py).** The fixer has 24 working `_fix_furbXXX` methods that
   pass the audit; the agent's `_transform_furbXXX` has only 9. Most
   issues are routed through the fixer first, so practical impact is
   less than the 81% NOOP number suggests. But for codes not in the fixer,
   the agent dispatch is a silent dead end.

1. **Refurb ground truth is in `refurb --explain <CODE>`.** Re-running
   this audit when refurb upgrades (currently v2.3.1) is cheap. The
   driver at `docs/audits/2026-06-12-furb-handler-audit-driver.py` can
   be re-invoked with `refurb` on PATH.

1. **The right fix for the dict itself is per-handler tests.** For each
   of the 9 CORRECT handlers, add a test. For each of the 44 NOOPs, either
   add a test (after fixing) or add an explicit `pytest.skip` with a
   reason. The audit log has the input/output pair for each code already;
   converting those into parametrized pytest cases is mechanical.
