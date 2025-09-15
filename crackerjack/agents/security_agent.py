from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
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

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.SECURITY, IssueType.REGEX_VALIDATION}

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.get_supported_types():
            return 0.0

        message_lower = issue.message.lower()

        if issue.type == IssueType.REGEX_VALIDATION:
            return 0.95

        if any(
            keyword in message_lower
            for keyword in (
                "validate-regex-patterns",
                "raw regex",
                "regex pattern",
                r"\g<",
                "replacement",
                "unsafe regex",
                "regex vulnerability",
                "redos",
            )
        ):
            return 0.95

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
                "pickle",
                "yaml.load",
                "md5",
                "sha1",
                "jwt_secret",
            )
        ):
            return 0.9

        enhanced_patterns = [
            "detect_security_keywords",
            "detect_crypto_weak_algorithms",
            "detect_hardcoded_credentials_advanced",
            "detect_subprocess_shell_injection",
            "detect_unsafe_pickle_usage",
        ]

        for pattern_name in enhanced_patterns:
            if SAFE_PATTERNS[pattern_name].test(issue.message):
                return 0.9

        if issue.file_path and any(
            keyword in issue.file_path.lower()
            for keyword in ("security", "auth", "crypto", "password", "token", "jwt")
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
            confidence = 0.95 if success else 0.4

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
            "regex_validation": self._fix_regex_validation_issues,
            "hardcoded_temp_paths": self._fix_hardcoded_temp_paths,
            "shell_injection": self._fix_shell_injection,
            "hardcoded_secrets": self._fix_hardcoded_secrets,
            "unsafe_yaml": self._fix_unsafe_yaml,
            "eval_usage": self._fix_eval_usage,
            "weak_crypto": self._fix_weak_crypto,
            "jwt_secrets": self._fix_jwt_secrets,
            "pickle_usage": self._fix_pickle_usage,
            "insecure_random": self._fix_insecure_random,
        }

        if (fix_method := vulnerability_fix_map.get(vulnerability_type)) is not None:
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

        if self._is_regex_validation_issue(issue):
            return "regex_validation"

        pattern_checks = self._check_enhanced_patterns(message)
        if pattern_checks:
            return pattern_checks

        bandit_checks = self._check_bandit_patterns(message)
        if bandit_checks:
            return bandit_checks

        legacy_checks = self._check_legacy_patterns(message)
        if legacy_checks:
            return legacy_checks

        if self._is_jwt_secret_issue(message):
            return "jwt_secrets"

        return "unknown"

    def _is_regex_validation_issue(self, issue: Issue) -> bool:
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

    def _check_enhanced_patterns(self, message: str) -> str | None:
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

    def _check_bandit_patterns(self, message: str) -> str | None:
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

    def _check_legacy_patterns(self, message: str) -> str | None:
        pattern_map = {
            "detect_hardcoded_temp_paths_basic": "hardcoded_temp_paths",
            "detect_hardcoded_secrets": "hardcoded_secrets",
            "detect_insecure_random_usage": "insecure_random",
        }

        for pattern_name, vulnerability_type in pattern_map.items():
            if SAFE_PATTERNS[pattern_name].test(message):
                return vulnerability_type

        return None

    def _is_jwt_secret_issue(self, message: str) -> bool:
        message_lower = message.lower()
        return "jwt" in message_lower and (
            "secret" in message_lower or "hardcoded" in message_lower
        )

    async def _fix_regex_validation_issues(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            await self._fix_regex_patterns_project_wide(fixes, files)
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return {"fixes": fixes, "files": files}

        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        original_content = content
        content = await self._apply_regex_pattern_fixes(content)

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Fixed unsafe regex patterns in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed regex patterns in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _fix_regex_patterns_project_wide(
        self, fixes: list[str], files: list[str]
    ) -> None:
        try:
            python_files = self._get_python_files_for_security_scan()
            await self._process_python_files_for_regex_fixes(python_files, fixes, files)
        except Exception as e:
            self.log(f"Error during project-wide regex fixes: {e}", "ERROR")

    def _get_python_files_for_security_scan(self) -> list[Path]:
        python_files = list(self.context.project_path.rglob("*.py"))
        return [
            f for f in python_files if not self._should_skip_file_for_security_scan(f)
        ]

    def _should_skip_file_for_security_scan(self, file_path: Path) -> bool:
        skip_patterns = [".venv", "__pycache__", ".git"]
        return any(part in str(file_path) for part in skip_patterns)

    async def _process_python_files_for_regex_fixes(
        self, python_files: list[Path], fixes: list[str], files: list[str]
    ) -> None:
        for file_path in python_files:
            await self._process_single_file_for_regex_fixes(file_path, fixes, files)

    async def _process_single_file_for_regex_fixes(
        self, file_path: Path, fixes: list[str], files: list[str]
    ) -> None:
        content = self.context.get_file_content(file_path)
        if not content:
            return

        original_content = content
        content = await self._apply_regex_pattern_fixes(content)

        if self._should_save_regex_fixes(content, original_content):
            await self._save_regex_fixes_to_file(file_path, content, fixes, files)

    def _should_save_regex_fixes(self, content: str, original_content: str) -> bool:
        return content != original_content

    async def _save_regex_fixes_to_file(
        self, file_path: Path, content: str, fixes: list[str], files: list[str]
    ) -> None:
        if self.context.write_file_content(file_path, content):
            fixes.append(f"Fixed unsafe regex patterns in {file_path}")
            files.append(str(file_path))
            self.log(f"Fixed regex patterns in {file_path}")

    async def _apply_regex_pattern_fixes(self, content: str) -> str:
        from crackerjack.services.regex_utils import (
            replace_unsafe_regex_with_safe_patterns,
        )

        try:
            fixed_content = replace_unsafe_regex_with_safe_patterns(content)
            return fixed_content
        except Exception as e:
            self.log(f"Error applying regex fixes: {e}", "ERROR")
            return content

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
        new_content = "\n".join(lines)

        if SAFE_PATTERNS["detect_hardcoded_temp_paths_basic"].test(new_content):
            new_content = SAFE_PATTERNS["replace_hardcoded_temp_paths"].apply(
                new_content
            )
            new_content = SAFE_PATTERNS["replace_hardcoded_temp_strings"].apply(
                new_content
            )
            new_content = SAFE_PATTERNS["replace_hardcoded_temp_single_quotes"].apply(
                new_content
            )
            new_content = SAFE_PATTERNS["replace_test_path_patterns"].apply(new_content)
            lines = new_content.split("\n")
            return lines, True

        return lines, False

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

        from crackerjack.services.regex_patterns import apply_security_fixes

        content = apply_security_fixes(content)

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
        return SAFE_PATTERNS["detect_hardcoded_secrets"].test(line)

    def _replace_hardcoded_secret_with_env_var(self, line: str) -> str:
        var_name_result = SAFE_PATTERNS["extract_variable_name_from_assignment"].apply(
            line
        )
        if var_name_result != line:  # Pattern matched and extracted variable name
            var_name = var_name_result
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

        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        content = SAFE_PATTERNS["fix_unsafe_yaml_load"].apply(content)

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

        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        content = SAFE_PATTERNS["fix_weak_md5_hash"].apply(content)
        content = SAFE_PATTERNS["fix_weak_sha1_hash"].apply(content)

        if content != original_content:
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Upgraded weak cryptographic hashes in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed weak crypto in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _fix_jwt_secrets(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
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
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Fixed hardcoded JWT secrets in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed JWT secrets in {issue.file_path}")

        return {"fixes": fixes, "files": files}

    async def _fix_pickle_usage(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
        if not content:
            return {"fixes": fixes, "files": files}

        fixes.append(
            f"Documented unsafe pickle usage in {issue.file_path} - manual review required"
        )

        if "pickle.load" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "pickle.load" in line and "# SECURITY: " not in line:
                    lines[i] = (
                        line + " # SECURITY: pickle.load is unsafe with untrusted data"
                    )
                    if self.context.write_file_content(file_path, "\n".join(lines)):
                        fixes.append(
                            f"Added security warning for pickle usage in {issue.file_path}"
                        )
                        files.append(str(file_path))
                        self.log(
                            f"Added security warning for pickle in {issue.file_path}"
                        )
                    break

        return {"fixes": fixes, "files": files}

    async def _fix_insecure_random(self, issue: Issue) -> dict[str, list[str]]:
        fixes: list[str] = []
        files: list[str] = []

        if not issue.file_path:
            return {"fixes": fixes, "files": files}

        file_path = Path(issue.file_path)
        content = self.context.get_file_content(file_path)
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
            if self.context.write_file_content(file_path, content):
                fixes.append(f"Fixed insecure random usage in {issue.file_path}")
                files.append(str(file_path))
                self.log(f"Fixed insecure random usage in {issue.file_path}")

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
        if not SAFE_PATTERNS["detect_insecure_random_usage"].test(content):
            return content

        content = self._add_secrets_import_if_needed(content)

        return SAFE_PATTERNS["fix_insecure_random_choice"].apply(content)

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
        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        return SAFE_PATTERNS["remove_debug_prints_with_secrets"].apply(content)


agent_registry.register(SecurityAgent)
