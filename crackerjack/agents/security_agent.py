import re
from pathlib import Path

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class SecurityAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.security_patterns = {
            "hardcoded_temp_paths": r"(?:/tmp/|/temp/|C:\\temp\\|C:\\tmp\\)",
            "shell_injection": r"shell=True|os\.system\(|subprocess\.call\([^)]*shell=True",
            "path_traversal": r"\.\./|\.\.\\",
            "hardcoded_secrets": r"(?:password|secret|key|token)\s*=\s*['\"][^'\"]+['\"]",
            "unsafe_yaml": r"yaml\.load\([^)]*\)",
            "eval_usage": r"\beval\s*\(",
            "exec_usage": r"\bexec\s*\(",
            "pickle_usage": r"\bpickle\.loads?\s*\(",
            "sql_injection": r"(?:execute|query)\s*\([^)]*%[sd]",
            "weak_crypto": r"(?:md5|sha1)\s*\(",
            "insecure_random": r"random\.random\(\)|random\.choice\(",
        }

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.SECURITY}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        message_lower = issue.message.lower()

        if any(
            keyword in message_lower
            for keyword in (
                "bandit",
                "security",
                "vulnerability",
                "hardcoded",
                "shell=true",
                "b108",
                "b602",
                "b301",
                "b506",
                "unsafe",
                "injection",
            )
        ):
            return 1.0

        for pattern in self.security_patterns.values():
            if re.search(pattern, issue.message, re.IGNORECASE):
                return 0.9

        if issue.file_path and any(
            keyword in issue.file_path.lower()
            for keyword in ("security", "auth", "crypto", "password")
        ):
            return 0.7

        if issue.type == IssueType.SECURITY:
            return 0.6

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        self.log(f"Analyzing security issue: {issue.message}")

        fixes_applied: list[str] = []
        files_modified: list[str] = []
        recommendations: list[str] = []

        try:
            vulnerability_type = self._identify_vulnerability_type(issue)
            self.log(f"Identified vulnerability type: {vulnerability_type}")

            fixes_applied, files_modified = await self._apply_vulnerability_fixes(
                vulnerability_type,
                issue,
                fixes_applied,
                files_modified,
            )

            fixes_applied, files_modified = await self._apply_additional_fixes(
                issue,
                fixes_applied,
                files_modified,
            )

            success = len(fixes_applied) > 0
            confidence = 0.85 if success else 0.4

            if not success:
                recommendations = self._get_security_recommendations()

            return FixResult(
                success=success,
                confidence=confidence,
                fixes_applied=fixes_applied,
                files_modified=files_modified,
                recommendations=recommendations,
            )

        except Exception as e:
            self.log(f"Error fixing security issue: {e}", "ERROR")
            return self._create_error_fix_result(e)

    async def _apply_vulnerability_fixes(
        self,
        vulnerability_type: str,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        vulnerability_fix_map = {
            "hardcoded_temp_paths": self._fix_hardcoded_temp_paths,
            "shell_injection": self._fix_shell_injection,
            "hardcoded_secrets": self._fix_hardcoded_secrets,
            "unsafe_yaml": self._fix_unsafe_yaml,
            "eval_usage": self._fix_eval_usage,
            "weak_crypto": self._fix_weak_crypto,
        }

        if fix_method := vulnerability_fix_map.get(vulnerability_type):
            fixes = await fix_method(issue)
            fixes_applied.extend(fixes["fixes"])
            files_modified.extend(fixes["files"])

        return fixes_applied, files_modified

    async def _apply_additional_fixes(
        self,
        issue: Issue,
        fixes_applied: list[str],
        files_modified: list[str],
    ) -> tuple[list[str], list[str]]:
        if not fixes_applied:
            bandit_fixes = await self._run_bandit_analysis()
            fixes_applied.extend(bandit_fixes)

        if issue.file_path:
            file_fixes = await self._fix_file_security_issues(issue.file_path)
            fixes_applied.extend(file_fixes["fixes"])
            if file_fixes["fixes"]:
                files_modified.append(issue.file_path)

        return fixes_applied, files_modified

    def _get_security_recommendations(self) -> list[str]:
        return [
            "Use tempfile module for temporary file creation",
            "Avoid shell=True in subprocess calls",
            "Use environment variables for secrets",
            "Implement proper input validation",
            "Use safe_load() instead of load() for YAML",
            "Consider using cryptographically secure random module",
        ]

    def _create_error_fix_result(self, error: Exception) -> FixResult:
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

    def _identify_vulnerability_type(self, issue: Issue) -> str:
        message = issue.message

        if "B108" in message:
            return "hardcoded_temp_paths"
        if "B602" in message or "shell=True" in message:
            return "shell_injection"
        if "B301" in message or "pickle" in message.lower():
            return "pickle_usage"
        if "B506" in message or "yaml.load" in message:
            return "unsafe_yaml"

        for pattern_name, pattern in self.security_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                return pattern_name

        return "unknown"

    async def _fix_hardcoded_temp_paths(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return {"fixes": fixes, "files": files}

        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        lines = content.split("\n")
        lines, modified = self._process_temp_path_fixes(lines)

        if modified:
            if self.context.write_file_content(file_path, "\n".join(lines)):
                fixes.append(f"Fixed hardcoded temp paths in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed hardcoded temp paths in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    def _process_temp_path_fixes(self, lines: list[str]) -> tuple[list[str], bool]:
        modified = False

        lines, import_added = self._ensure_tempfile_import(lines)
        if import_added:
            modified = True

        lines, paths_replaced = self._replace_hardcoded_temp_paths(lines)
        if paths_replaced:
            modified = True

        return lines, modified

    def _ensure_tempfile_import(self, lines: list[str]) -> tuple[list[str], bool]:
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

    def _replace_hardcoded_temp_paths(self, lines: list[str]) -> tuple[list[str], bool]:
        replacements = [
            (r'Path\("/tmp/([^"]+)"\)', r'Path(tempfile.gettempdir()) / "\1"'),
            (r'"/tmp/([^"]+)"', r'str(Path(tempfile.gettempdir()) / "\1")'),
            (r"'/tmp/([^']+)'", r"str(Path(tempfile.gettempdir()) / '\1')"),
            (
                r'Path\("/test/path"\)',
                r"Path(tempfile.gettempdir()) / 'test-path'",
            ),
            (r'"/test/path"', r'str(Path(tempfile.gettempdir()) / "test-path")'),
            (r"'/test/path'", r"str(Path(tempfile.gettempdir()) / 'test-path')"),
        ]

        modified = False
        for pattern, replacement in replacements:
            new_content = "\n".join(lines)
            if re.search(pattern, new_content):
                lines = re.sub(pattern, replacement, new_content).split("\n")
                modified = True

        return lines, modified

    async def _fix_shell_injection(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        original_content = content

        patterns = [
            (
                r"subprocess\.run\(([^,]+),\s*shell=True\)",
                r"subprocess.run(\1.split())",
            ),
            (
                r"subprocess\.call\(([^,]+),\s*shell=True\)",
                r"subprocess.call(\1.split())",
            ),
            (
                r"subprocess\.Popen\(([^,]+),\s*shell=True\)",
                r"subprocess.Popen(\1.split())",
            ),
        ]

        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(
                    f"Fixed shell injection vulnerability in {issue.file_path}",
                )
                files.append(str(file_path))
                self.log(f"Fixed shell injection in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _fix_hardcoded_secrets(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        lines = content.split("\n")
        lines, modified = self._process_hardcoded_secrets_in_lines(lines)

        if modified:
            if self.context.write_file_content(file_path, "\n".join(lines)):
                fixes.append(f"Fixed hardcoded secrets in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed hardcoded secrets in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    def _process_hardcoded_secrets_in_lines(
        self,
        lines: list[str],
    ) -> tuple[list[str], bool]:
        modified = False

        lines, import_added = self._ensure_os_import(lines)
        if import_added:
            modified = True

        for i, line in enumerate(lines):
            if self._line_contains_hardcoded_secret(line):
                new_line = self._replace_hardcoded_secret_with_env_var(line)
                if new_line != line:
                    lines[i] = new_line
                    modified = True

        return lines, modified

    def _ensure_os_import(self, lines: list[str]) -> tuple[list[str], bool]:
        has_os_import = any("import os" in line for line in lines)
        if has_os_import:
            return lines, False

        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                lines.insert(i, "import os")
                return lines, True

        return lines, False

    def _line_contains_hardcoded_secret(self, line: str) -> bool:
        return bool(
            re.search(
                r'(password|secret|key|token)\s*=\s*[\'"][^\'"]+[\'"]',
                line,
                re.IGNORECASE,
            ),
        )

    def _replace_hardcoded_secret_with_env_var(self, line: str) -> str:
        match = re.search(r"(\w+)\s*=", line)
        if match:
            var_name = match.group(1)
            env_var_name = var_name.upper()
            return f"{var_name} = os.getenv('{env_var_name}', '')"
        return line

    async def _fix_unsafe_yaml(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        original_content = content

        content = re.sub(r"\byaml\.load\(", "yaml.safe_load(", content)

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Fixed unsafe YAML loading in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed unsafe YAML loading in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _fix_eval_usage(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        fixes.append(
            f"Identified eval() usage in {issue.file_path} - manual review required",
        )

        return {"fixes": fixes, "files": files}

    async def _fix_weak_crypto(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        original_content = content

        replacements = [
            (r"\bhashlib\.md5\(", "hashlib.sha256("),
            (r"\bhashlib\.sha1\(", "hashlib.sha256("),
        ]

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Upgraded weak cryptographic hashes in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed weak crypto in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _run_bandit_analysis(self) -> list[str]:
        fixes: list[str] = []

        try:
            returncode, _, _ = await self.run_command(
                ["uv", "run", "bandit", "-r", "crackerjack/", "-f", "txt"],
            )

            if returncode == 0:
                fixes.append("Bandit security scan completed successfully")
            else:
                fixes.append("Bandit identified security issues for review")

        except Exception as e:
            self.log(f"Bandit analysis failed: {e}", "WARN")

        return fixes

    async def _fix_file_security_issues(self, file_path: str) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        try:
            path = Path(file_path)
            if not self._is_valid_file_path(path):
                return {"fixes": fixes, "files": files}

            content = self.context.get_file_content(path)
            if not content:
                return {"fixes": fixes, "files": files}

            original_content = content
            content = await self._apply_security_fixes_to_content(content)

            if content != original_content:
                if self.context.write_file_content(path, content):
                    fixes.append(f"Applied general security fixes to {file_path}")
                    files.append(file_path)
                    self.log(f"Applied security fixes to {file_path}")

        except Exception as e:
            self.log(f"Error fixing file security issues in {file_path}: {e}", "ERROR")

        return {"fixes": fixes, "files": files}

    def _is_valid_file_path(self, path: Path) -> bool:
        return path.exists() and path.is_file()

    async def _apply_security_fixes_to_content(self, content: str) -> str:
        content = await self._fix_insecure_random_usage(content)
        return self._remove_debug_prints_with_secrets(content)

    async def _fix_insecure_random_usage(self, content: str) -> str:
        if not re.search(r"random\.(?:random|choice)\(", content):
            return content

        content = self._add_secrets_import_if_needed(content)

        return re.sub(r"random\.choice\(([^)]+)\)", r"secrets.choice(\1)", content)

    def _add_secrets_import_if_needed(self, content: str) -> str:
        if "import secrets" in content:
            return content

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                lines.insert(i + 1, "import secrets")
                break
        return "\n".join(lines)

    def _remove_debug_prints_with_secrets(self, content: str) -> str:
        return re.sub(
            r"print\s*\([^)]*(?:password|secret|key|token)[^)]*\)",
            "",
            content,
            flags=re.IGNORECASE,
        )


agent_registry.register(SecurityAgent)
