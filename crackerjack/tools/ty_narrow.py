"""Mechanical None-narrowing for ty ``unsupported-operator`` and
``not-subscriptable`` errors.

Where ``ty_imports`` adds missing imports and ``ty_cleanup`` strips
redundant annotations, this module inserts a *None-coercion* default
into expressions whose operands may be ``None``.

Scope (deliberately narrow):

* ``<expr> in <var: T | None>`` → ``<expr> in (<var> or <default>)``
* ``<expr> not in <var: T | None>`` → ``<expr> not in (<var> or <default>)``
* ``<var: dict | None>["k"]`` → ``(<var> or {})["k"]``
* Where ``T`` is one of: ``str``, ``dict``, ``list``, ``set`` (the
  types whose default-value substitution is safe — i.e., ``""``,
  ``{}``, ``[]``, ``set()`` are all valid empty-container values).

Out of scope (handed to tier-3 / human):

* Arithmetic operators (``int + int | None``) — needs early-return
  or assertion, not a silent default.
* Subscript-on-None where the LHS isn't a dict (``list[int] | None``) —
  defaulting with ``[]`` would still mismatch the element type.
* Subscript-on-None where the LHS isn't a bare identifier
  (``self.cache["k"]``, ``func()["k"]``) — needs instance-narrow
  reasoning, not a default substitution.
* Unions like ``int | str`` (no ``None``) — cannot be narrowed
  with ``or`` because the LHS is already truthy.
* Method-call receivers (``<var>.method()``) — needs isinstance
  narrowing, not default substitution.

Design note on safety:

The ``or``-substitution preserves the operator's *return type* (it
already returned ``bool`` for ``in``). For ``not-subscriptable``,
``(<var> or {})["k"]`` returns the same value type as ``<var>["k"]``
when ``<var>`` is non-None — only the None-arm is replaced with an
empty dict, which gives a ``KeyError`` rather than a ``TypeError``.
This is the cheapest possible semantic change that resolves the
type error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUTO_FIX_CODES: frozenset[str] = frozenset(
    {"unsupported-operator", "not-subscriptable"}
)


# Container-type → empty-default-value mapping. Only types whose
# empty value is a valid "default" for ``in`` membership testing.
_DEFAULT_BY_TYPE: dict[str, str] = {
    "str": '""',
    "dict": "{}",
    "list": "[]",
    "set": "set()",
    "tuple": "()",
    "bytes": 'b""',
    "frozenset": "frozenset()",
}


# ---------------------------------------------------------------------------
# Diagnostic parsing
# ---------------------------------------------------------------------------

# Matches: `Operator `OP` is not supported between objects of type `LHS` and `RHS`
_OPERATOR_RE = re.compile(
    r"^Operator `(?P<op>[^`]+)` is not supported between objects of type "
    r"`(?P<lhs>[^`]+)` and `(?P<rhs>[^`]+)`\s*$"
)


@dataclass(frozen=True)
class UnsupportedOperatorSite:
    file: Path
    line: int
    col: int
    operator: str  # e.g. "in", "not in", "+"
    lhs_type: str  # e.g. 'Literal["x"]'
    rhs_type: str  # e.g. 'str | None'


# Matches the prefix up to the message body (mirrors ty_cleanup's pattern).
_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"error\[unsupported-operator\]\s+"
    r"(?P<msg>.+)$"
)


def parse_ty_unsupported_operator(line: str) -> UnsupportedOperatorSite | None:
    """Parse one ty concise output line for ``unsupported-operator``.

    Returns ``None`` for non-matches OR for operators other than
    ``in`` / ``not in`` (we don't mechanically narrow other operators).
    """
    match = _LINE_RE.match(line.strip())
    if not match:
        return None
    msg_match = _OPERATOR_RE.match(match["msg"])
    if not msg_match:
        return None
    op = msg_match["op"]
    if op not in {"in", "not in"}:
        return None
    rhs = msg_match["rhs"]
    if "None" not in rhs:
        return None
    return UnsupportedOperatorSite(
        file=Path(match["file"]),
        line=int(match["line"]),
        col=int(match["col"]),
        operator=op,
        lhs_type=msg_match["lhs"],
        rhs_type=rhs,
    )


# ---------------------------------------------------------------------------
# Candidate identification
# ---------------------------------------------------------------------------


# Match ``<expr> in <var>`` / ``<expr> not in <var>`` where <var> is
# a bare identifier (not a chained expression). We deliberately
# avoid attribute access (``x.y``), subscripts (``x[y]``), or calls
# (``f(x)``) — those need LLM reasoning.
_IN_RE = re.compile(
    r"^(?P<lhs>.+?)\s+(?P<op>not\s+in|in)\s+(?P<var>[A-Za-z_]\w*)\s*(?P<rest>.*)$"
)


def _extract_container_type(union_type: str) -> str | None:
    """Given a type like ``"str | None"`` or ``"dict[str, int] | None"``,
    return the non-None container type if it's one we can default-substitute.

    Returns ``None`` for unions without a recognizable container base,
    or for unions that have *more than one* non-None arm (ambiguous default).
    """
    arms = [a.strip() for a in union_type.split("|")]
    non_none = [a for a in arms if a != "None"]
    if len(non_none) != 1:
        return None
    base = non_none[0]
    # Strip subscript parameters (dict[str, int] -> dict)
    base_name = base.split("[", 1)[0].strip()
    return base_name if base_name in _DEFAULT_BY_TYPE else None


@dataclass(frozen=True)
class NarrowFix:
    """A mechanical narrowing fix ready to apply."""

    line: int
    col: int
    operator: str
    rhs_type: str
    var_name: str
    default_value: str  # e.g. '""' for str | None
    original: str  # the source line, unchanged
    replacement: str  # the rewritten line


def find_in_operator_candidates(
    content: str,
    line: int,
    operator: str,
    rhs_type: str,
) -> NarrowFix | None:
    """Find a candidate for ``<expr> in <var>`` narrowing at ``line``.

    Returns ``None`` if:

    * the RHS union type isn't a simple ``T | None`` with T in
      ``_DEFAULT_BY_TYPE``
    * the suspect RHS isn't a bare identifier (we won't touch
      chained expressions)
    * the suspect is already wrapped in ``(...)`` (already narrowed)
    """
    container = _extract_container_type(rhs_type)
    if container is None:
        return None

    lines = content.splitlines()
    if line < 1 or line > len(lines):
        return None
    original = lines[line - 1]

    match = _IN_RE.match(original)
    if not match:
        return None

    lhs = match["lhs"].strip()
    var = match["var"]
    rest = match["rest"]

    # The variable must be a bare identifier (regex already enforces).
    # We additionally reject if it's already wrapped or default-valued.
    if var in {"[]", "{}", '""', "set()"}:
        return None

    default = _DEFAULT_BY_TYPE[container]
    modified_in = f"{lhs} {operator} ({var} or {default})"
    # Preserve trailing characters after the var (e.g., `# comment`).
    replacement = f"{modified_in}{rest}"
    return NarrowFix(
        line=line,
        col=1,
        operator=operator,
        rhs_type=rhs_type,
        var_name=var,
        default_value=default,
        original=original,
        replacement=replacement,
    )


# ---------------------------------------------------------------------------
# Subscript narrowing (``<var: dict | None>["k"]`` → ``(<var> or {})["k"]``)
# ---------------------------------------------------------------------------


# Match ``<identifier>["<string-literal>"]``. LHS is captured
# non-greedily so it stops at the first ``[``; trailing characters
# after ``]`` (e.g., inline comments) go in ``rest``. The bare-
# identifier constraint is enforced below with a separate regex.
_SUBSCRIPT_RE = re.compile(r'^(?P<lhs>.+?)\[(?P<key>"[^"]+")\](?P<rest>.*)$')


def find_subscript_candidates(
    content: str,
    line: int,
    rhs_type: str,
) -> NarrowFix | None:
    """Find a candidate for ``<var>["key"]`` narrowing at ``line``.

    Returns ``None`` if:

    * the RHS union isn't a simple ``dict | None`` (other container
      unions need element-type reasoning — ``list[int] | None`` would
      default to ``[]`` but the subscripted element is ``int``)
    * the LHS isn't a bare identifier (``self.cache`` or ``func()``
      need LLM reasoning)
    * the key isn't a string literal (``value[some_var]`` is a
      dynamic key whose type we can't pre-validate)
    """
    # Require a single non-None arm whose base is ``dict``. Subscript on
    # ``dict`` is safe with ``{}`` because both sides return the value
    # type (subscript on empty dict raises ``KeyError``, which is
    # strictly better than ``TypeError`` on ``None``).
    if "dict" not in rhs_type or "None" not in rhs_type:
        return None
    arms = [a.strip() for a in rhs_type.split("|") if a.strip() != "None"]
    if len(arms) != 1 or not arms[0].startswith("dict"):
        return None

    lines = content.splitlines()
    if line < 1 or line > len(lines):
        return None
    original = lines[line - 1]

    match = _SUBSCRIPT_RE.match(original)
    if not match:
        return None
    lhs = match["lhs"].strip()
    key = match["key"]
    rest = match["rest"]

    # Bare identifier only (no chaining like ``self.cache`` or ``func()``).
    if not re.match(r"^[A-Za-z_]\w*$", lhs):
        return None

    default = "{}"
    modified = f"({lhs} or {default})[{key}]"
    replacement = f"{modified}{rest}"
    return NarrowFix(
        line=line,
        col=1,
        operator="subscript",
        rhs_type=rhs_type,
        var_name=lhs,
        default_value=default,
        original=original,
        replacement=replacement,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_narrow_fix(file_path: Path, fix: NarrowFix) -> bool:
    """Apply the narrowing fix to ``file_path``.

    Idempotent: returns ``False`` if the replacement line is already
    present (the file looks already-fixed). Returns ``True`` after a
    successful write.
    """
    content = file_path.read_text(encoding="utf-8")
    # ``splitlines()`` (not ``split("\\n")``) — splits without producing
    # a trailing empty string when content ends in a newline.
    lines = content.splitlines()
    idx = fix.line - 1
    if idx < 0 or idx >= len(lines):
        return False
    # ``fix.replacement`` is the *line content* (no trailing newline);
    # callers may have passed it with a newline, so strip.
    replacement_line = fix.replacement.rstrip("\n")
    if lines[idx] == replacement_line:
        return False  # already applied
    lines[idx] = replacement_line
    new_content = "\n".join(lines)
    # Preserve trailing newline if the original had one.
    if content.endswith("\n"):
        new_content += "\n"
    if new_content == content:
        return False
    file_path.write_text(new_content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Driver (mirrors ty_imports.fix_unresolved_references)
# ---------------------------------------------------------------------------


def fix_unsupported_operators(
    file_path: Path,
    sites: list[UnsupportedOperatorSite],
) -> tuple[int, list[UnsupportedOperatorSite]]:
    """Apply ``apply_narrow_fix`` for every site that yields a candidate.

    Returns ``(fixes_applied, unresolved_sites)`` — the latter is the
    subset we couldn't fix and that should be handed to the LLM tier.
    """
    content = file_path.read_text(encoding="utf-8")
    fixes_applied = 0
    unresolved: list[UnsupportedOperatorSite] = []
    for site in sites:
        candidate = find_in_operator_candidates(
            content,
            line=site.line,
            operator=site.operator,
            rhs_type=site.rhs_type,
        )
        if candidate is None:
            unresolved.append(site)
            continue
        if apply_narrow_fix(file_path, candidate):
            fixes_applied += 1
            # Reload content so subsequent fixes see the updated file.
            content = file_path.read_text(encoding="utf-8")
    return fixes_applied, unresolved


def fix_not_subscriptable(
    file_path: Path,
    sites: list[tuple[int, str]],
) -> tuple[int, list[tuple[int, str]]]:
    """Apply ``apply_narrow_fix`` for every ``not-subscriptable`` site.

    Mirrors ``fix_unsupported_operators`` but for subscript diagnostics.
    Each site is a ``(line, rhs_type)`` tuple — subscript diagnostics
    don't carry an operator or LHS type, so a slim tuple shape is
    enough.

    Returns ``(fixes_applied, unresolved_sites)`` — the latter is the
    subset we couldn't fix and that should be handed to the LLM tier.
    """
    content = file_path.read_text(encoding="utf-8")
    fixes_applied = 0
    unresolved: list[tuple[int, str]] = []
    for line, rhs_type in sites:
        candidate = find_subscript_candidates(
            content,
            line=line,
            rhs_type=rhs_type,
        )
        if candidate is None:
            unresolved.append((line, rhs_type))
            continue
        if apply_narrow_fix(file_path, candidate):
            fixes_applied = fixes_applied + 1
            content = file_path.read_text(encoding="utf-8")
    return fixes_applied, unresolved
