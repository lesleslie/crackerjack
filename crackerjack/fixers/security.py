"""Deterministic security-vulnerability regex fixer.

Extracted from ``crackerjack.agents.security_agent.SecurityAgent``, which
(unlike ``RefactoringAgent``/``PerformanceAgent``) does not delegate to any
``agents/helpers/*`` classes -- it is self-contained aside from a thin
``FileContextReader`` helper (an async, cache-backed file reader) used only
by ``execute_fix_plan``.

What was intentionally dropped versus the original ``SecurityAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``__init__`` (which only ever
  constructed the now-unused ``FileContextReader``), ``can_handle``, and
  ``get_supported_types`` -- these only ever decided *whether* and *how
  confidently* this fixer should run for a given ``Issue``; that routing job
  belongs to whatever calls into this module now, not to the module itself.
  Note that ``can_handle``'s confidence scoring is independent of the real
  vulnerability-classification logic used for fixing (``_identify_vulnerability_type``
  and its ``_check_*``/``_is_*`` helpers below) -- the latter is kept because it
  decides *which* real fixer to run, not *whether* to run at all.
- ``agent_registry.register(SecurityAgent)`` -- registry plumbing.
- ``self.log(...)`` calls throughout -- ``SubAgent.log`` is a no-op ``pass``
  on the base class, so these calls had no observable effect; dropped along
  with the rest of the coordinator plumbing (same treatment as
  ``crackerjack/fixers/performance.py``).
- ``AgentContext``-specific file I/O: ``AgentContext.get_file_content``'s
  path-traversal check, and ``AgentContext.write_file_content``'s
  path-traversal check, ``wrap_long_lines`` post-processing (which itself
  imports from the to-be-removed ``crackerjack.ai_fix`` package), and
  syntax/duplicate-top-level-definition validation -- replaced with direct
  ``pathlib.Path`` reads/writes via ``_read_file``/``_write_file`` below.
  Real file I/O is still performed; only the framework wrapper around it is
  gone. Likewise ``FileContextReader``'s async cached read (used only by
  ``execute_fix_plan`` via ``_read_file_context``) is replaced with a direct
  synchronous read inline in ``execute_fix_plan``.
- ``AgentContext.project_path``-derived subprocess ``cwd``: the original
  ``SubAgent.run_command`` always ran external tools (``uv lock
  --upgrade-package ...`` in ``_fix_dependency_vulnerability``, ``uv run
  bandit ...`` in ``_run_bandit_analysis``) with ``cwd=self.context.project_path``.
  Task 22a restored this pinning: ``fix_security_issue`` now takes an
  explicit ``project_root: Path`` parameter, threaded through
  ``_apply_vulnerability_fixes``/``_apply_additional_fixes`` down to
  ``_fix_dependency_vulnerability``/``_run_bandit_analysis``, which pass it
  as ``cwd`` to ``_run_command`` (itself now requiring an explicit ``cwd``
  parameter, not defaulted). Real subprocess execution is still performed,
  with the same async/timeout semantics as the original
  ``SubAgent.run_command``.
- Redundant repeated local imports: the original re-imports
  ``from crackerjack.services.regex_patterns import SAFE_PATTERNS`` inside
  several methods (``_fix_unsafe_yaml``, ``_fix_weak_crypto``,
  ``_remove_debug_prints_with_secrets``) even though the same name is already
  imported at module scope. Consolidated into the single top-level import
  below; this is a no-op cleanup (same module object either way), not a
  behavior change.

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``fix_security_issue``
below (same identify/dispatch/apply-additional-fixes flow, minus the
``self``/``AgentContext`` plumbing).

``execute_fix_plan`` is kept (per the plan's precedent: ``SecurityAgent`` is
one of four agent classes -- alongside ``ArchitectAgent``, ``DocumentationAgent``,
and ``FormattingAgent`` -- with its own ``FixPlan``/``ChangeSpec`` applicator,
independent of ``planning_agent.py``'s plan-construction logic). Two
pre-existing behavioral quirks in it are preserved verbatim, not fixed, per
CLAUDE.md Rule 7 ("preserve functional requirements... fix the technical
issue, not the requirements"):

1. It replaces ``old_code`` by doing ``file_content.replace(old_code,
   change.new_code)`` -- a whole-file, all-occurrences string replace --
   rather than slicing the file at ``change.line_range`` (contrast this with
   ``refactoring.py``'s ``_apply_standard_fix_change``, which does the
   line-range slice correctly). If the exact ``old_code`` snippet occurs more
   than once in the file, *every* occurrence gets replaced, not just the one
   at the reported line range.
2. ``_check_new_code_security`` never actually rejects a change: it scans
   ``new_code`` for danger substrings (``password``, ``secret``, ``api_key``,
   ``token``, ``private_key``) purely to log a warning via the (no-op)
   ``SubAgent.log`` hook, and always returns ``True`` regardless of what it
   finds. It is effectively a dead/no-op security gate in the original code.

``_should_skip_file_for_security_scan`` also preserves a pre-existing bug:
it does ``part in file_path`` where ``file_path`` is a ``pathlib.Path``, not
a ``str``. ``Path`` does not implement ``__contains__``/``__iter__``, so this
raises ``TypeError`` at runtime whenever ``_get_python_files_for_security_scan``
finds at least one candidate file (exercised only by the project-wide regex
scan branch of ``_fix_regex_validation_issues``, i.e. when ``issue.file_path``
is unset). Preserved verbatim, not fixed, and covered by a test that asserts
the ``TypeError`` -- see ``tests/fixers/test_security.py``.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import suppress
from pathlib import Path

from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType
from crackerjack.services.regex_patterns import SAFE_PATTERNS, apply_security_fixes
from crackerjack.services.regex_utils import replace_unsafe_regex_with_safe_patterns


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


async def _run_command(
    cmd: list[str],
    cwd: Path,
    timeout: int = 300,
) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        return (
            process.returncode or 0,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )
    except TimeoutError:
        return (-1, "", "Command timed out")
    except Exception as e:
        return (-1, "", f"Command failed: {e}")


def _is_urllib_false_positive(issue: Issue) -> bool:
    if not issue.message:
        return False

    message_lower = issue.message.lower()

    if "urllib" not in message_lower:
        return False

    config_url_indicators = [
        "base_url",
        "api_url",
        "endpoint",
        "config",
        "settings",
        "localhost",
        "127.0.0.1",
        "http://localhost",
        "https://localhost",
        "ollama_base_url",
        "ollama",
        "embedding",
        "mcp",
        "api",
    ]

    safe_file_patterns = [
        "embeddings",
        "embedding",
        "ollama",
        "mcp",
        "config",
        "settings",
        "integration",
        "ai/",
        "services/",
    ]

    if issue.file_path:
        file_lower = issue.file_path.lower()
        if any(indicator in file_lower for indicator in safe_file_patterns):
            return True

    if issue.line_number and issue.line_number > 0 and issue.file_path:
        with suppress(Exception):
            content = _read_file(issue.file_path)
            if content:
                lines = content.split("\n")
                if issue.line_number <= len(lines):
                    line = lines[issue.line_number - 1]
                    line_lower = line.lower()
                    if any(
                        indicator in line_lower for indicator in config_url_indicators
                    ):
                        return True
                    if "ollama_base_url" in content or "ollama" in line_lower:
                        return True

    return False


def _is_regex_validation_issue(issue: Issue) -> bool:
    if issue.type == IssueType.REGEX_VALIDATION:
        return True

    message_lower = issue.message.lower()
    return any(
        keyword in message_lower
        for keyword in (
            "validate-regex-patterns",
            "raw regex",
            "unsafe regex",
            r"\g<",
            "redos",
        )
    )


def _check_enhanced_patterns(message: str) -> str | None:
    pattern_map = {
        "detect_crypto_weak_algorithms": "weak_crypto",
        "detect_hardcoded_credentials_advanced": "hardcoded_secrets",
        "detect_subprocess_shell_injection": "shell_injection",
        "detect_unsafe_pickle_usage": "pickle_usage",
        "detect_regex_redos_vulnerable": "regex_validation",
    }

    for pattern_name, vulnerability_type in pattern_map.items():
        if SAFE_PATTERNS[pattern_name].test(message):
            return vulnerability_type

    return None


def _check_bandit_patterns(message: str) -> str | None:
    if "B108" in message:
        return "hardcoded_temp_paths"
    if "B602" in message or "shell=True" in message:
        return "shell_injection"
    if "B301" in message or "pickle" in message.lower():
        return "pickle_usage"
    if "B506" in message or "yaml.load" in message:
        return "unsafe_yaml"
    if any(crypto in message.lower() for crypto in ("md5", "sha1", "des", "rc4")):
        return "weak_crypto"

    return None


def _check_legacy_patterns(message: str) -> str | None:
    pattern_map = {
        "detect_hardcoded_temp_paths_basic": "hardcoded_temp_paths",
        "detect_hardcoded_secrets": "hardcoded_secrets",
        "detect_insecure_random_usage": "insecure_random",
    }

    for pattern_name, vulnerability_type in pattern_map.items():
        if SAFE_PATTERNS[pattern_name].test(message):
            return vulnerability_type

    return None


def _is_jwt_secret_issue(message: str) -> bool:
    message_lower = message.lower()
    return "jwt" in message_lower and (
        "secret" in message_lower or "hardcoded" in message_lower
    )


def _is_dependency_vulnerability(issue: Issue) -> bool:
    if issue.stage != "pip-audit":
        return False
    if not issue.message:
        return False
    return bool(re.match(r"^CVE-\d{4}-\d+", issue.message))


def _identify_vulnerability_type(issue: Issue) -> str:
    message = issue.message

    if _is_urllib_false_positive(issue):
        return "urllib_false_positive"

    if _is_regex_validation_issue(issue):
        return "regex_validation"

    pattern_checks = _check_enhanced_patterns(message)
    if pattern_checks:
        return pattern_checks

    bandit_checks = _check_bandit_patterns(message)
    if bandit_checks:
        return bandit_checks

    legacy_checks = _check_legacy_patterns(message)
    if legacy_checks:
        return legacy_checks

    if _is_jwt_secret_issue(message):
        return "jwt_secrets"

    if _is_dependency_vulnerability(issue):
        return "dependency_vulnerability"

    return "unknown"


def _extract_vulnerability_package(issue: Issue) -> str | None:
    if not issue.details:
        return None
    for detail in issue.details:
        if detail.startswith("package: "):
            return detail[len("package: ") :]
    return None


async def _fix_dependency_vulnerability(
    issue: Issue, project_root: Path
) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    package_name = _extract_vulnerability_package(issue)
    if not package_name:
        fixes.append(f"Cannot auto-fix {issue.message}: unable to extract package name")
        return {"fixes": fixes, "files": files}

    try:
        returncode, _stdout, stderr = await _run_command(
            ["uv", "lock", "--upgrade-package", package_name],
            cwd=project_root,
            timeout=120,
        )

        if returncode == 0:
            fixes.append(f"Upgraded {package_name} to resolve {issue.message}")
            files.append("uv.lock")
        else:
            fixes.append(
                f"uv lock --upgrade-package {package_name} failed "
                f"(exit {returncode}): {stderr[:200] if stderr else 'no output'}"
            )
    except Exception as e:
        fixes.append(f"Error upgrading {package_name}: {e}")

    return {"fixes": fixes, "files": files}


def _apply_regex_pattern_fixes_content(content: str) -> str:
    try:
        return replace_unsafe_regex_with_safe_patterns(content)
    except Exception:
        return content


async def _apply_regex_pattern_fixes(content: str) -> str:
    return _apply_regex_pattern_fixes_content(content)


async def _fix_regex_validation_issues(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        await _fix_regex_patterns_project_wide(fixes, files)
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return {"fixes": fixes, "files": files}

    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content
    content = await _apply_regex_pattern_fixes(content)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Fixed unsafe regex patterns in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_regex_patterns_project_wide(
    fixes: list[str],
    files: list[str],
) -> None:
    with suppress(Exception):
        python_files = _get_python_files_for_security_scan()
        await _process_python_files_for_regex_fixes(python_files, fixes, files)


def _get_python_files_for_security_scan() -> list[Path]:
    from crackerjack.tools._git_utils import get_files_by_extension

    python_files = get_files_by_extension([".py"], use_git=True)
    return [f for f in python_files if not _should_skip_file_for_security_scan(f)]


def _should_skip_file_for_security_scan(file_path: Path) -> bool:
    skip_patterns = [".venv", "__pycache__", ".git"]
    return any(part in file_path for part in skip_patterns)  # type: ignore


async def _process_python_files_for_regex_fixes(
    python_files: list[Path],
    fixes: list[str],
    files: list[str],
) -> None:
    for file_path in python_files:
        await _process_single_file_for_regex_fixes(file_path, fixes, files)


async def _process_single_file_for_regex_fixes(
    file_path: Path,
    fixes: list[str],
    files: list[str],
) -> None:
    content = _read_file(file_path)
    if not content:
        return

    original_content = content
    content = await _apply_regex_pattern_fixes(content)

    if _should_save_regex_fixes(content, original_content):
        await _save_regex_fixes_to_file(file_path, content, fixes, files)


def _should_save_regex_fixes(content: str, original_content: str) -> bool:
    return content != original_content


async def _save_regex_fixes_to_file(
    file_path: Path,
    content: str,
    fixes: list[str],
    files: list[str],
) -> None:
    if _write_file(file_path, content):
        fixes.append(f"Fixed unsafe regex patterns in {file_path}")
        files.append(str(file_path))


async def _fix_hardcoded_temp_paths(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return {"fixes": fixes, "files": files}

    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    lines = content.split("\n")
    lines, modified = _process_temp_path_fixes(lines)

    if modified:
        if _write_file(file_path, "\n".join(lines)):
            fixes.append(f"Fixed hardcoded temp paths in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


def _process_temp_path_fixes(lines: list[str]) -> tuple[list[str], bool]:
    modified = False

    lines, import_added = _ensure_tempfile_import(lines)
    if import_added:
        modified = True

    lines, paths_replaced = _replace_hardcoded_temp_paths(lines)
    if paths_replaced:
        modified = True

    return lines, modified


def _ensure_tempfile_import(lines: list[str]) -> tuple[list[str], bool]:
    has_tempfile_import = any("import tempfile" in line for line in lines)
    if has_tempfile_import:
        return lines, False

    import_section_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            import_section_end = i + 1
        elif line.strip() == "" and import_section_end > 0:
            break

    lines.insert(import_section_end, "import tempfile")
    return lines, True


def _replace_hardcoded_temp_paths(lines: list[str]) -> tuple[list[str], bool]:
    new_content = "\n".join(lines)

    if SAFE_PATTERNS["detect_hardcoded_temp_paths_basic"].test(new_content):
        new_content = SAFE_PATTERNS["replace_hardcoded_temp_paths"].apply(new_content)
        new_content = SAFE_PATTERNS["replace_hardcoded_temp_strings"].apply(new_content)
        new_content = SAFE_PATTERNS["replace_hardcoded_temp_single_quotes"].apply(
            new_content,
        )
        new_content = SAFE_PATTERNS["replace_test_path_patterns"].apply(new_content)
        lines = new_content.split("\n")
        return lines, True

    return lines, False


async def _fix_shell_injection(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content
    content = apply_security_fixes(content)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Fixed shell injection vulnerability in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_hardcoded_secrets(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    lines = content.split("\n")
    lines, modified = _process_hardcoded_secrets_in_lines(lines)

    if modified:
        if _write_file(file_path, "\n".join(lines)):
            fixes.append(f"Fixed hardcoded secrets in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


def _process_hardcoded_secrets_in_lines(
    lines: list[str],
) -> tuple[list[str], bool]:
    modified = False

    lines, import_added = _ensure_os_import(lines)
    if import_added:
        modified = True

    for i, line in enumerate(lines):
        if _line_contains_hardcoded_secret(line):
            new_line = _replace_hardcoded_secret_with_env_var(line)
            if new_line != line:
                lines[i] = new_line
                modified = True

    return lines, modified


def _ensure_os_import(lines: list[str]) -> tuple[list[str], bool]:
    has_os_import = any("import os" in line for line in lines)
    if has_os_import:
        return lines, False

    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            lines.insert(i, "import os")
            return lines, True

    return lines, False


def _line_contains_hardcoded_secret(line: str) -> bool:
    return SAFE_PATTERNS["detect_hardcoded_secrets"].test(line)


def _replace_hardcoded_secret_with_env_var(line: str) -> str:
    var_name_result = SAFE_PATTERNS["extract_variable_name_from_assignment"].apply(line)
    if var_name_result != line:
        var_name = var_name_result
        env_var_name = var_name.upper()
        return f"{var_name} = os.getenv('{env_var_name}', '')"
    return line


async def _fix_unsafe_yaml(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content
    content = SAFE_PATTERNS["fix_unsafe_yaml_load"].apply(content)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Fixed unsafe YAML loading in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_eval_usage(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    fixes.append(
        f"Identified eval() usage in {issue.file_path} - manual review required",
    )

    return {"fixes": fixes, "files": files}


async def _fix_weak_crypto(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content
    content = SAFE_PATTERNS["fix_weak_md5_hash"].apply(content)
    content = SAFE_PATTERNS["fix_weak_sha1_hash"].apply(content)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Upgraded weak cryptographic hashes in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_jwt_secrets(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content

    content = SAFE_PATTERNS["fix_hardcoded_jwt_secret"].apply(content)

    if "os.getenv" in content and "import os" not in content:
        lines = content.split("\n")
        import_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                import_index = i + 1
        lines.insert(import_index, "import os")
        content = "\n".join(lines)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Fixed hardcoded JWT secrets in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_pickle_usage(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    fixes.append(
        f"Documented unsafe pickle usage in {issue.file_path} - manual review required",
    )

    if "pickle.load" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pickle.load" in line and "# SECURITY: " not in line:
                lines[i] = (
                    line + " # SECURITY: pickle.load is unsafe with untrusted data"
                )
                if _write_file(file_path, "\n".join(lines)):
                    fixes.append(
                        f"Added security warning for pickle usage in {issue.file_path}",
                    )
                    files.append(str(file_path))
                break

    return {"fixes": fixes, "files": files}


async def _fix_insecure_random(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    original_content = content

    content = SAFE_PATTERNS["fix_insecure_random_choice"].apply(content)

    if "secrets.choice" in content and "import secrets" not in content:
        lines = content.split("\n")
        import_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                import_index = i + 1
        lines.insert(import_index, "import secrets")
        content = "\n".join(lines)

    if content != original_content:
        if _write_file(file_path, content):
            fixes.append(f"Fixed insecure random usage in {issue.file_path}")
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _fix_urllib_false_positive(issue: Issue) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    if not issue.file_path:
        return {"fixes": fixes, "files": files}

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return {"fixes": fixes, "files": files}

    if not issue.line_number or issue.line_number <= 0:
        return {"fixes": fixes, "files": files}

    lines = content.split("\n")
    line_idx = issue.line_number - 1

    if line_idx >= len(lines):
        return {"fixes": fixes, "files": files}

    line = lines[line_idx]

    if "# nosem" in line or "# nosemgrep" in line:
        fixes.append(
            f"URLlib false positive already marked in {issue.file_path}:{issue.line_number}"
        )
        return {"fixes": fixes, "files": files}

    if "urlopen" in line or "urllib.request" in line or "urllib" in line:
        nosem_comment = (
            "# nosem: python.lang.security.audit.dynamic-urllib-use-detected"
        )
        if "# nosem" in line or "# nosemgrep" in line:
            pass
        elif "# nosec" in line:
            lines[line_idx] = line.rstrip() + " " + nosem_comment
        else:
            lines[line_idx] = line.rstrip() + " # nosec: B310 " + nosem_comment

        new_content = "\n".join(lines)
        if _write_file(file_path, new_content):
            fixes.append(
                f"Added # nosec and # nosem comments to urllib usage in {issue.file_path}:{issue.line_number}"
            )
            files.append(str(file_path))

    return {"fixes": fixes, "files": files}


async def _run_bandit_analysis(project_root: Path) -> list[str]:
    fixes: list[str] = []

    with suppress(Exception):
        returncode, _, _ = await _run_command(
            ["uv", "run", "bandit", "-r", "crackerjack/", "-f", "txt"],
            cwd=project_root,
        )

        if returncode == 0:
            fixes.append("Bandit security scan completed successfully")
        else:
            fixes.append("Bandit identified security issues for review")

    return fixes


def _is_valid_file_path(path: Path) -> bool:
    return path.exists() and path.is_file()


async def _fix_insecure_random_usage(content: str) -> str:
    if not SAFE_PATTERNS["detect_insecure_random_usage"].test(content):
        return content

    content = _add_secrets_import_if_needed(content)

    return SAFE_PATTERNS["fix_insecure_random_choice"].apply(content)


def _add_secrets_import_if_needed(content: str) -> str:
    if "import secrets" in content:
        return content

    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(("import ", "from ")):
            lines.insert(i + 1, "import secrets")
            break
    return "\n".join(lines)


def _remove_debug_prints_with_secrets(content: str) -> str:
    return SAFE_PATTERNS["remove_debug_prints_with_secrets"].apply(content)


async def _apply_security_fixes_to_content(content: str) -> str:
    content = await _fix_insecure_random_usage(content)
    return _remove_debug_prints_with_secrets(content)


async def _fix_file_security_issues(file_path: str) -> dict[str, list[str]]:
    fixes: list[str] = []
    files: list[str] = []

    with suppress(Exception):
        path = Path(file_path)
        if not _is_valid_file_path(path):
            return {"fixes": fixes, "files": files}

        content = _read_file(path)
        if not content:
            return {"fixes": fixes, "files": files}

        original_content = content
        content = await _apply_security_fixes_to_content(content)

        if content != original_content:
            if _write_file(path, content):
                fixes.append(f"Applied general security fixes to {file_path}")
                files.append(file_path)

    return {"fixes": fixes, "files": files}


def _get_security_recommendations() -> list[str]:
    return [
        "Use centralized SAFE_PATTERNS for regex operations to prevent ReDoS attacks",
        "Avoid raw regex patterns with vulnerable replacement syntax like \\g<1>",
        "Use tempfile module for temporary file creation instead of hardcoded paths",
        "Avoid shell=True in subprocess calls to prevent command injection",
        "Store secrets in environment variables using os.getenv(), never hardcode them",
        "Replace weak cryptographic algorithms (MD5, SHA1, DES, RC4) with stronger alternatives",
        "Use secrets module instead of random for cryptographically secure operations",
        "Replace unsafe yaml.load() with yaml.safe_load() to prevent code execution",
        "Avoid pickle.load() with untrusted data as it can execute arbitrary code",
        "Use JWT secrets from environment variables, never hardcode them",
        "Implement proper input validation and sanitization for all user inputs",
        "Add security comments to document potential risks in legacy code",
        "Run bandit security scanner regularly to identify new vulnerabilities",
        "Review all subprocess calls for potential injection vulnerabilities",
        "Ensure all cryptographic operations use secure algorithms and proper key management",
    ]


def _create_error_fix_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Failed to fix security issue: {error}"],
        recommendations=[
            "Manual security review may be required",
            "Consider running bandit security scanner",
            "Review code for common security anti-patterns",
        ],
    )


async def _apply_vulnerability_fixes(
    vulnerability_type: str,
    issue: Issue,
    project_root: Path,
    fixes_applied: list[str],
    files_modified: list[str],
) -> tuple[list[str], list[str]]:
    if vulnerability_type == "dependency_vulnerability":
        fixes = await _fix_dependency_vulnerability(issue, project_root)
        fixes_applied.extend(fixes["fixes"])
        files_modified.extend(fixes["files"])
        return fixes_applied, files_modified

    vulnerability_fix_map = {
        "regex_validation": _fix_regex_validation_issues,
        "hardcoded_temp_paths": _fix_hardcoded_temp_paths,
        "shell_injection": _fix_shell_injection,
        "hardcoded_secrets": _fix_hardcoded_secrets,
        "unsafe_yaml": _fix_unsafe_yaml,
        "eval_usage": _fix_eval_usage,
        "weak_crypto": _fix_weak_crypto,
        "jwt_secrets": _fix_jwt_secrets,
        "pickle_usage": _fix_pickle_usage,
        "insecure_random": _fix_insecure_random,
        "urllib_false_positive": _fix_urllib_false_positive,
    }

    if (fix_method := vulnerability_fix_map.get(vulnerability_type)) is not None:
        fixes = await fix_method(issue)
        fixes_applied.extend(fixes["fixes"])
        files_modified.extend(fixes["files"])

    return fixes_applied, files_modified


async def _apply_additional_fixes(
    issue: Issue,
    project_root: Path,
    fixes_applied: list[str],
    files_modified: list[str],
) -> tuple[list[str], list[str]]:
    if not fixes_applied:
        bandit_fixes = await _run_bandit_analysis(project_root)
        fixes_applied.extend(bandit_fixes)

    if issue.file_path:
        file_fixes = await _fix_file_security_issues(issue.file_path)
        fixes_applied.extend(file_fixes["fixes"])
        if file_fixes["fixes"]:
            files_modified.append(issue.file_path)

    return fixes_applied, files_modified


async def fix_security_issue(issue: Issue, project_root: Path) -> FixResult:
    fixes_applied: list[str] = []
    files_modified: list[str] = []
    recommendations: list[str] = []

    try:
        vulnerability_type = _identify_vulnerability_type(issue)

        fixes_applied, files_modified = await _apply_vulnerability_fixes(
            vulnerability_type,
            issue,
            project_root,
            fixes_applied,
            files_modified,
        )

        fixes_applied, files_modified = await _apply_additional_fixes(
            issue,
            project_root,
            fixes_applied,
            files_modified,
        )

        success = bool(fixes_applied)
        confidence = 0.95 if success else 0.4

        if not success:
            recommendations = _get_security_recommendations()

        return FixResult(
            success=success,
            confidence=confidence,
            fixes_applied=fixes_applied,
            files_modified=files_modified,
            recommendations=recommendations,
        )

    except Exception as e:
        return _create_error_fix_result(e)


async def _check_new_code_security(code: str) -> bool:
    # Preserved verbatim from SecurityAgent._check_new_code_security: this
    # never actually rejects anything. It only ever used the detected danger
    # patterns to log a warning via the (no-op) SubAgent.log hook, and always
    # returns True regardless of what it finds -- effectively a dead/no-op
    # security gate in the original code. Kept as-is per CLAUDE.md Rule 7.
    danger_patterns = [
        "password",
        "secret",
        "api_key",
        "token",
        "private_key",
    ]
    code_lower = code.lower()
    for pattern in danger_patterns:
        if pattern in code_lower:
            lines = code.split("\n")
            for line in lines:
                if pattern in line.lower() and not line.strip().startswith("#"):
                    pass

    return True


async def execute_fix_plan(plan: FixPlan) -> FixResult:
    if not plan.changes:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Plan has no changes to apply"],
            recommendations=["PlanningAgent should generate actual changes"],
        )

    if not plan.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path in plan"],
        )

    try:
        file_content = Path(plan.file_path).read_text(encoding="utf-8")
    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {e}"],
        )

    applied_changes = []
    failed_changes = []
    for i, change in enumerate(plan.changes):
        try:
            lines = file_content.split("\n")
            if change.line_range[0] < 1 or change.line_range[1] > len(lines):
                failed_changes.append(
                    f"Change {i}: Invalid line range {change.line_range}"
                )
                continue

            old_lines = lines[change.line_range[0] - 1 : change.line_range[1]]
            old_code = "\n".join(old_lines)

            # NOTE: whole-file, all-occurrences replace -- preserved verbatim
            # from SecurityAgent.execute_fix_plan. See module docstring quirk
            # (1): if `old_code` occurs more than once in the file, every
            # occurrence is replaced, not just the one at `change.line_range`.
            new_content = file_content.replace(old_code, change.new_code)

            if await _check_new_code_security(new_content):
                success = _write_file(plan.file_path, new_content)
                if success:
                    applied_changes.append(f"Change {i}: {change.reason}")
                else:
                    failed_changes.append(f"Change {i} failed: {change.reason}")
            else:
                failed_changes.append(
                    f"Change {i} rejected: security validation failed"
                )
        except Exception as e:
            failed_changes.append(f"Change {i} failed: {e}")

    success = len(applied_changes) == len(plan.changes)
    confidence = 0.8 if success else 0.0
    remaining_issues = (
        []
        if success
        else failed_changes or [f"Failed to apply planned changes to {plan.file_path}"]
    )

    return FixResult(
        success=success,
        confidence=confidence,
        fixes_applied=applied_changes,
        remaining_issues=remaining_issues,
        files_modified=[plan.file_path] if success else [],
    )


__all__ = [
    "ChangeSpec",
    "FixPlan",
    "execute_fix_plan",
    "fix_security_issue",
]
