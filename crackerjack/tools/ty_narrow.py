
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


AUTO_FIX_CODES: frozenset[str] = frozenset(
    {"unsupported-operator", "not-subscriptable"}
)


_DEFAULT_BY_TYPE: dict[str, str] = {
    "str": '""',
    "dict": "{}",
    "list": "[]",
    "set": "set()",
    "tuple": "()",
    "bytes": 'b""',
    "frozenset": "frozenset()",
}


_OPERATOR_RE = re.compile(
    r"^Operator `(?P<op>[^`]+)` is not supported between objects of type "
    r"`(?P<lhs>[^`]+)` and `(?P<rhs>[^`]+)`\s*$"
)


_INDENT_RE = re.compile(r"^(?P<indent>[ \t]*)")


@dataclass(frozen=True)
class UnsupportedOperatorSite:
    file: Path
    line: int
    col: int
    operator: str
    lhs_type: str
    rhs_type: str


_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"error\[unsupported-operator\]\s+"
    r"(?P<msg>.+)$"
)


def parse_ty_unsupported_operator(line: str) -> UnsupportedOperatorSite | None:
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


_IN_RE = re.compile(
    r"^(?P<lhs>.+?)\s+(?P<op>not\s+in|in)\s+(?P<var>[A-Za-z_]\w*)\s*(?P<rest>.*)$"
)


def _extract_container_type(union_type: str) -> str | None:
    arms = [a.strip() for a in union_type.split("|")]
    non_none = [a for a in arms if a != "None"]
    if len(non_none) != 1:
        return None
    base = non_none[0]

    base_name = base.split("[", 1)[0].strip()
    return base_name if base_name in _DEFAULT_BY_TYPE else None


@dataclass(frozen=True)
class NarrowFix:

    line: int
    col: int
    operator: str
    rhs_type: str
    var_name: str
    default_value: str
    original: str
    replacement: str


def find_in_operator_candidates(
    content: str,
    line: int,
    operator: str,
    rhs_type: str,
) -> NarrowFix | None:
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


    if var in {"[]", "{}", '""', "set()"}:
        return None

    default = _DEFAULT_BY_TYPE[container]
    modified_in = f"{lhs} {operator} ({var} or {default})"

    replacement = f"{modified_in}{rest}"

    indent = _INDENT_RE.match(original)["indent"]
    if not replacement.startswith(indent):
        replacement = f"{indent}{replacement}"
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


_SUBSCRIPT_RE = re.compile(r'^(?P<lhs>.+?)\[(?P<key>"[^"]+")\](?P<rest>.*)$')


def find_subscript_candidates(
    content: str,
    line: int,
    rhs_type: str,
) -> NarrowFix | None:


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


    if not re.match(r"^[A-Za-z_]\w*$", lhs):
        return None

    default = "{}"
    modified = f"({lhs} or {default})[{key}]"
    replacement = f"{modified}{rest}"

    indent = _INDENT_RE.match(original)["indent"]
    if not replacement.startswith(indent):
        replacement = f"{indent}{replacement}"
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


def apply_narrow_fix(
    file_path: Path,
    fix: NarrowFix,
    *,
    project_root: Path | None = None,
) -> bool:
    if project_root is not None:
        resolved = file_path.resolve(strict=False)
        root_resolved = project_root.resolve(strict=False)
        if not resolved.is_relative_to(root_resolved):
            logger.warning(
                "Refusing to write %s outside project root %s",
                resolved,
                root_resolved,
            )
            return False
    content = file_path.read_text(encoding="utf-8")


    lines = content.splitlines()
    idx = fix.line - 1
    if idx < 0 or idx >= len(lines):
        return False


    replacement_line = fix.replacement.rstrip("\n")
    if lines[idx] == replacement_line:
        return False
    lines[idx] = replacement_line
    new_content = "\n".join(lines)

    if content.endswith("\n"):
        new_content += "\n"
    if new_content == content:
        return False
    file_path.write_text(new_content, encoding="utf-8")
    return True


def fix_unsupported_operators(
    file_path: Path,
    sites: list[UnsupportedOperatorSite],
) -> tuple[int, list[UnsupportedOperatorSite]]:
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

            content = file_path.read_text(encoding="utf-8")
    return fixes_applied, unresolved


def fix_not_subscriptable(
    file_path: Path,
    sites: list[tuple[int, str]],
) -> tuple[int, list[tuple[int, str]]]:
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
