"""Tests for crackerjack.fixers.security.

Ported from tests/unit/agents/test_security_agent.py, keeping only the cases
that exercise real SAFE_PATTERNS-based regex fixing, file transforms, and
the FixPlan/ChangeSpec applicator (``execute_fix_plan``). Cases exercising
SubAgent/coordinator dispatch (``can_handle``, ``get_supported_types``,
``SecurityAgent.__init__``) were dropped, since that machinery no longer
exists -- see the module docstring of ``crackerjack/fixers/security.py`` for
the full kept/dropped rationale, including two pre-existing behavioral
quirks preserved verbatim (not fixed) per CLAUDE.md Rule 7.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import security
from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "sec-test",
        "type": IssueType.SECURITY,
        "severity": Priority.HIGH,
        "message": "Security issue",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestIdentifyVulnerabilityType:
    def test_identify_regex_validation_by_type(self) -> None:
        issue = _issue(type=IssueType.REGEX_VALIDATION, message="Invalid regex pattern")

        assert security._identify_vulnerability_type(issue) == "regex_validation"

    def test_identify_regex_validation_by_keyword(self) -> None:
        issue = _issue(message="validate-regex-patterns found unsafe pattern")

        assert security._identify_vulnerability_type(issue) == "regex_validation"

    def test_identify_hardcoded_temp_paths(self) -> None:
        issue = _issue(message="Bandit B108: hardcoded temp path detected")

        assert security._identify_vulnerability_type(issue) == "hardcoded_temp_paths"

    def test_identify_shell_injection(self) -> None:
        issue = _issue(message="Bandit B602: shell=True detected")

        assert security._identify_vulnerability_type(issue) == "shell_injection"

    def test_identify_pickle_usage(self) -> None:
        issue = _issue(message="Bandit B301: pickle usage with untrusted data")

        assert security._identify_vulnerability_type(issue) == "pickle_usage"

    def test_identify_unsafe_yaml(self) -> None:
        issue = _issue(message="Bandit B506: yaml.load() usage detected")

        assert security._identify_vulnerability_type(issue) == "unsafe_yaml"

    def test_identify_weak_crypto(self) -> None:
        issue = _issue(message="MD5 hash function is cryptographically broken")

        assert security._identify_vulnerability_type(issue) == "weak_crypto"

    def test_identify_jwt_secrets(self) -> None:
        issue = _issue(message="Hardcoded JWT secret key detected")

        assert security._identify_vulnerability_type(issue) == "jwt_secrets"

    def test_identify_dependency_vulnerability(self) -> None:
        issue = _issue(
            message="CVE-2024-12345 affects this package",
            stage="pip-audit",
        )

        assert (
            security._identify_vulnerability_type(issue) == "dependency_vulnerability"
        )

    def test_identify_unknown(self) -> None:
        issue = _issue(message="Some other security issue")

        assert security._identify_vulnerability_type(issue) == "unknown"


class TestPatternChecks:
    def test_is_regex_validation_issue_by_type(self) -> None:
        issue = _issue(type=IssueType.REGEX_VALIDATION, message="Pattern issue")

        assert security._is_regex_validation_issue(issue) is True

    def test_is_regex_validation_issue_by_keyword(self) -> None:
        issue = _issue(message="raw regex pattern detected")

        assert security._is_regex_validation_issue(issue) is True

    def test_is_not_regex_validation_issue(self) -> None:
        issue = _issue(message="shell injection vulnerability")

        assert security._is_regex_validation_issue(issue) is False

    def test_check_bandit_patterns_b108(self) -> None:
        assert (
            security._check_bandit_patterns("Bandit B108: hardcoded temp")
            == "hardcoded_temp_paths"
        )

    def test_check_bandit_patterns_b602(self) -> None:
        assert (
            security._check_bandit_patterns("Bandit B602: shell=True")
            == "shell_injection"
        )

    def test_check_bandit_patterns_b301(self) -> None:
        assert (
            security._check_bandit_patterns("Bandit B301: pickle usage")
            == "pickle_usage"
        )

    def test_check_bandit_patterns_b506(self) -> None:
        assert (
            security._check_bandit_patterns("Bandit B506: yaml.load") == "unsafe_yaml"
        )

    def test_check_bandit_patterns_crypto(self) -> None:
        assert (
            security._check_bandit_patterns("Using MD5 hash function") == "weak_crypto"
        )

    def test_check_bandit_patterns_no_match(self) -> None:
        assert security._check_bandit_patterns("Some other issue") is None

    def test_is_jwt_secret_issue(self) -> None:
        assert security._is_jwt_secret_issue("Hardcoded JWT secret key") is True

    def test_is_not_jwt_secret_issue(self) -> None:
        assert security._is_jwt_secret_issue("Some other secret") is False

    def test_check_enhanced_patterns_weak_crypto(self) -> None:
        # Real SAFE_PATTERNS["detect_crypto_weak_algorithms"] match, no mocks.
        assert (
            security._check_enhanced_patterns("hashlib.md5() usage detected")
            == "weak_crypto"
        )

    def test_check_enhanced_patterns_hardcoded_secrets(self) -> None:
        assert (
            security._check_enhanced_patterns('password: "hardcoded_password_xyz"')
            == "hardcoded_secrets"
        )

    def test_check_enhanced_patterns_shell_injection(self) -> None:
        assert (
            security._check_enhanced_patterns("subprocess.run(cmd, shell=True)")
            == "shell_injection"
        )

    def test_check_enhanced_patterns_pickle_usage(self) -> None:
        assert security._check_enhanced_patterns("pickle.load(file)") == "pickle_usage"

    def test_check_enhanced_patterns_regex_redos(self) -> None:
        assert (
            security._check_enhanced_patterns("Vulnerable pattern (a+)* detected")
            == "regex_validation"
        )

    def test_check_enhanced_patterns_no_match(self) -> None:
        assert (
            security._check_enhanced_patterns("This is just informational text") is None
        )

    def test_check_legacy_patterns_temp_paths(self) -> None:
        assert (
            security._check_legacy_patterns("Found reference to /tmp/myfile.txt")
            == "hardcoded_temp_paths"
        )

    def test_check_legacy_patterns_hardcoded_secrets(self) -> None:
        assert (
            security._check_legacy_patterns("password = 'secret123'")
            == "hardcoded_secrets"
        )

    def test_check_legacy_patterns_insecure_random(self) -> None:
        assert (
            security._check_legacy_patterns("random.choice(items) call found")
            == "insecure_random"
        )

    def test_check_legacy_patterns_no_match(self) -> None:
        assert security._check_legacy_patterns("nothing interesting here") is None


class TestIsUrllibFalsePositive:
    def test_no_urllib_in_message(self) -> None:
        issue = _issue(message="Some unrelated security issue")

        assert security._is_urllib_false_positive(issue) is False

    def test_safe_file_pattern_short_circuits(self) -> None:
        issue = _issue(
            message="urllib usage flagged by bandit",
            file_path="/project/services/embeddings/client.py",
        )

        assert security._is_urllib_false_positive(issue) is True

    def test_line_content_indicator_from_real_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "downloader.py"
        test_file.write_text(
            "def fetch():\n"
            "    resp = urllib.request.urlopen(base_url)\n"
            "    return resp\n"
        )
        issue = _issue(
            message="urllib usage flagged by bandit",
            file_path=str(test_file),
            line_number=2,
        )

        assert security._is_urllib_false_positive(issue) is True

    def test_no_indicator_returns_false(self, tmp_path: Path) -> None:
        test_file = tmp_path / "downloader.py"
        test_file.write_text(
            "def fetch():\n    resp = urllib.request.urlopen(remote_target)\n"
        )
        issue = _issue(
            message="urllib usage flagged by bandit",
            file_path=str(test_file),
            line_number=2,
        )

        assert security._is_urllib_false_positive(issue) is False


class TestFixRegexValidationIssues:
    async def test_replaces_unsafe_re_sub_with_safe_pattern(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "import re\n\n\n"
            "def foo(text):\n"
            '    result = re.sub(r"(\\w+)\\s*-\\s*(\\w+)", r"\\1-\\2", text)\n'
            "    return result\n"
        )
        issue = _issue(
            type=IssueType.REGEX_VALIDATION,
            message="raw regex pattern detected",
            file_path=str(test_file),
        )

        result = await security._fix_regex_validation_issues(issue)

        assert result["fixes"] == [f"Fixed unsafe regex patterns in {test_file}"]
        assert result["files"] == [str(test_file)]
        new_content = test_file.read_text()
        assert "from crackerjack.services.regex_patterns import SAFE_PATTERNS" in (
            new_content
        )
        assert "SAFE_PATTERNS['fix_hyphenated_names'].apply(text)" in new_content

    async def test_no_file_path_and_no_change_is_noop(self) -> None:
        # No file_path -> falls through to the project-wide scan branch,
        # which silently swallows any error (see module docstring re:
        # _should_skip_file_for_security_scan's pre-existing TypeError bug).
        issue = _issue(type=IssueType.REGEX_VALIDATION, message="raw regex")

        result = await security._fix_regex_validation_issues(issue)

        assert result == {"fixes": [], "files": []}

    async def test_missing_file_returns_no_fixes(self, tmp_path: Path) -> None:
        issue = _issue(
            type=IssueType.REGEX_VALIDATION,
            message="raw regex",
            file_path=str(tmp_path / "missing.py"),
        )

        result = await security._fix_regex_validation_issues(issue)

        assert result == {"fixes": [], "files": []}


class TestShouldSkipFileForSecurityScan:
    def test_raises_type_error_pre_existing_bug(self) -> None:
        """`part in file_path` treats a Path as though it supported `in`;
        Path has no __contains__/__iter__, so this raises. Preserved
        verbatim from SecurityAgent per CLAUDE.md Rule 7 -- not fixed."""
        with pytest.raises(TypeError):
            security._should_skip_file_for_security_scan(Path("/repo/.venv/foo.py"))


class TestFixHardcodedTempPaths:
    async def test_replaces_tmp_path_and_adds_tempfile_import(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text('import os\n\npath = "/tmp/myfile.txt"\n')
        issue = _issue(
            message="Bandit B108: hardcoded temp path", file_path=str(test_file)
        )

        result = await security._fix_hardcoded_temp_paths(issue)

        assert result["fixes"] == [f"Fixed hardcoded temp paths in {test_file}"]
        new_content = test_file.read_text()
        assert "import tempfile" in new_content
        assert 'str(Path(tempfile.gettempdir()) / "myfile.txt")' in new_content

    async def test_no_file_path_is_noop(self) -> None:
        issue = _issue(message="Bandit B108")

        result = await security._fix_hardcoded_temp_paths(issue)

        assert result == {"fixes": [], "files": []}


class TestFixShellInjection:
    async def test_removes_shell_true(self, tmp_path: Path) -> None:
        test_file = tmp_path / "runner.py"
        test_file.write_text("import subprocess\n\nsubprocess.run(cmd, shell=True)\n")
        issue = _issue(message="Bandit B602: shell=True", file_path=str(test_file))

        result = await security._fix_shell_injection(issue)

        assert result["fixes"] == [
            f"Fixed shell injection vulnerability in {test_file}"
        ]
        assert test_file.read_text() == (
            "import subprocess\n\nsubprocess.run(cmd.split())\n"
        )


class TestFixHardcodedSecrets:
    async def test_replaces_secret_with_env_var_and_adds_os_import(
        self, tmp_path: Path
    ) -> None:
        # `_ensure_os_import` (ported verbatim) only inserts "import os"
        # ahead of an *existing* import/from line -- it does nothing if the
        # file has no imports at all. Use a file with a pre-existing import
        # so both the secret replacement and the import insertion fire.
        test_file = tmp_path / "config.py"
        test_file.write_text("import sys\n\npassword = 'secret123'\n")
        issue = _issue(message="Hardcoded password", file_path=str(test_file))

        result = await security._fix_hardcoded_secrets(issue)

        assert result["fixes"] == [f"Fixed hardcoded secrets in {test_file}"]
        new_content = test_file.read_text()
        assert "import os" in new_content
        assert "password = os.getenv('PASSWORD', '')" in new_content

    async def test_no_existing_import_line_skips_os_import_pre_existing_quirk(
        self, tmp_path: Path
    ) -> None:
        """Preserved verbatim: `_ensure_os_import` only inserts "import os"
        ahead of an existing import/from line. A file with no imports at
        all still gets its secret replaced with `os.getenv(...)`, but the
        `import os` line is silently never added."""
        test_file = tmp_path / "config.py"
        test_file.write_text("password = 'secret123'\n")
        issue = _issue(message="Hardcoded password", file_path=str(test_file))

        result = await security._fix_hardcoded_secrets(issue)

        assert result["fixes"] == [f"Fixed hardcoded secrets in {test_file}"]
        new_content = test_file.read_text()
        assert "import os" not in new_content
        assert "password = os.getenv('PASSWORD', '')" in new_content


class TestFixUnsafeYaml:
    async def test_replaces_yaml_load_with_safe_load(self, tmp_path: Path) -> None:
        test_file = tmp_path / "loader.py"
        test_file.write_text("data = yaml.load(f)\n")
        issue = _issue(message="Bandit B506: yaml.load", file_path=str(test_file))

        result = await security._fix_unsafe_yaml(issue)

        assert result["fixes"] == [f"Fixed unsafe YAML loading in {test_file}"]
        assert test_file.read_text() == "data = yaml.safe_load(f)\n"


class TestFixEvalUsage:
    async def test_returns_manual_review_message(self) -> None:
        issue = _issue(message="eval() usage detected", file_path="module.py")

        result = await security._fix_eval_usage(issue)

        assert result["files"] == []
        assert "manual review required" in result["fixes"][0]
        assert "module.py" in result["fixes"][0]


class TestFixWeakCrypto:
    async def test_upgrades_md5_and_sha1_to_sha256(self, tmp_path: Path) -> None:
        test_file = tmp_path / "hasher.py"
        test_file.write_text("a = hashlib.md5(data)\nb = hashlib.sha1(data)\n")
        issue = _issue(message="MD5 is weak", file_path=str(test_file))

        result = await security._fix_weak_crypto(issue)

        assert result["fixes"] == [f"Upgraded weak cryptographic hashes in {test_file}"]
        assert test_file.read_text() == (
            "a = hashlib.sha256(data)\nb = hashlib.sha256(data)\n"
        )


class TestFixJwtSecrets:
    async def test_replaces_hardcoded_jwt_secret(self, tmp_path: Path) -> None:
        test_file = tmp_path / "auth.py"
        test_file.write_text('JWT_SECRET = "hardcoded-secret"\n')
        issue = _issue(message="Hardcoded JWT secret", file_path=str(test_file))

        result = await security._fix_jwt_secrets(issue)

        assert result["fixes"] == [f"Fixed hardcoded JWT secrets in {test_file}"]
        new_content = test_file.read_text()
        assert "import os" in new_content
        assert 'JWT_SECRET = os.getenv("JWT_SECRET", "")' in new_content


class TestFixPickleUsage:
    async def test_adds_security_comment_to_pickle_load(self, tmp_path: Path) -> None:
        test_file = tmp_path / "loader.py"
        test_file.write_text("data = pickle.load(f)\n")
        issue = _issue(message="Bandit B301: pickle", file_path=str(test_file))

        result = await security._fix_pickle_usage(issue)

        assert any("manual review required" in fix for fix in result["fixes"])
        assert any("Added security warning" in fix for fix in result["fixes"])
        assert "# SECURITY: pickle.load is unsafe with untrusted data" in (
            test_file.read_text()
        )


class TestFixInsecureRandom:
    async def test_replaces_random_choice_with_secrets_choice(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "picker.py"
        test_file.write_text("item = random.choice(items)\n")
        issue = _issue(message="Insecure random usage", file_path=str(test_file))

        result = await security._fix_insecure_random(issue)

        assert result["fixes"] == [f"Fixed insecure random usage in {test_file}"]
        new_content = test_file.read_text()
        assert "import secrets" in new_content
        assert "item = secrets.choice(items)" in new_content


class TestFixUrllibFalsePositive:
    async def test_adds_nosec_and_nosem_comments(self, tmp_path: Path) -> None:
        test_file = tmp_path / "downloader.py"
        test_file.write_text(
            "def fetch():\n    resp = urllib.request.urlopen(base_url)\n"
        )
        issue = _issue(
            message="urllib usage flagged",
            file_path=str(test_file),
            line_number=2,
        )

        result = await security._fix_urllib_false_positive(issue)

        assert result["files"] == [str(test_file)]
        new_content = test_file.read_text()
        assert "# nosec: B310" in new_content
        assert (
            "# nosem: python.lang.security.audit.dynamic-urllib-use-detected"
            in new_content
        )

    async def test_already_marked_line_is_noop(self, tmp_path: Path) -> None:
        test_file = tmp_path / "downloader.py"
        test_file.write_text(
            "def fetch():\n"
            "    resp = urllib.request.urlopen(base_url)  # nosem: already-marked\n"
        )
        issue = _issue(
            message="urllib usage flagged",
            file_path=str(test_file),
            line_number=2,
        )

        result = await security._fix_urllib_false_positive(issue)

        assert "already marked" in result["fixes"][0]
        assert result["files"] == []


class TestFixDependencyVulnerability:
    async def test_no_package_name_reports_cannot_fix(self, tmp_path: Path) -> None:
        issue = _issue(message="CVE-2024-99999 found", stage="pip-audit")

        result = await security._fix_dependency_vulnerability(issue, tmp_path)

        assert result["files"] == []
        assert "unable to extract package name" in result["fixes"][0]

    async def test_successful_upgrade(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        issue = _issue(
            message="CVE-2024-99999 found",
            stage="pip-audit",
            details=["package: some-package"],
        )

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            assert cmd == ["uv", "lock", "--upgrade-package", "some-package"]
            assert cwd == tmp_path
            assert timeout == 120
            return (0, "", "")

        monkeypatch.setattr(security, "_run_command", fake_run_command)

        result = await security._fix_dependency_vulnerability(issue, tmp_path)

        assert result["files"] == ["uv.lock"]
        assert "Upgraded some-package" in result["fixes"][0]

    async def test_failed_upgrade_reports_stderr(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        issue = _issue(
            message="CVE-2024-99999 found",
            stage="pip-audit",
            details=["package: some-package"],
        )

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (1, "", "no matching version")

        monkeypatch.setattr(security, "_run_command", fake_run_command)

        result = await security._fix_dependency_vulnerability(issue, tmp_path)

        assert result["files"] == []
        assert "failed" in result["fixes"][0]
        assert "no matching version" in result["fixes"][0]


class TestRunCommandCwdPinning:
    """Regression coverage for Task 22a: the original ``SubAgent.run_command``
    always pinned ``cwd=self.context.project_path``; the extraction dropped
    it. These tests exercise the real ``asyncio.create_subprocess_exec`` call
    (not a monkeypatched ``_run_command``) to prove ``cwd`` is genuinely
    threaded through to the subprocess invocation for the project-wide
    (no specific file target) path -- the exact scenario the original review
    flagged as untested.
    """

    async def test_run_command_pins_cwd_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import asyncio

        marker = tmp_path / "marker.txt"
        marker.write_text("marker")

        captured: dict[str, object] = {}
        real_create_subprocess_exec = asyncio.create_subprocess_exec

        async def spying_create_subprocess_exec(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return await real_create_subprocess_exec(*args, **kwargs)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", spying_create_subprocess_exec
        )

        returncode, stdout, _stderr = await security._run_command(
            ["ls", "marker.txt"], cwd=tmp_path
        )

        assert captured["cwd"] == tmp_path
        assert returncode == 0
        assert "marker.txt" in stdout

    async def test_run_bandit_analysis_passes_cwd_through_to_subprocess(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Mutation-style verification (Task 17 precedent): confirm the
        # `cwd` kwarg observed by the real asyncio call chain matches the
        # `project_root` passed into `_run_bandit_analysis` -- the
        # project-wide entry point that has no per-file target at all.
        captured_cwd: list[Path | None] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            captured_cwd.append(cwd)
            return (0, "", "")

        monkeypatch.setattr(security, "_run_command", fake_run_command)

        await security._run_bandit_analysis(tmp_path)

        assert captured_cwd == [tmp_path]


class TestRunBanditAnalysis:
    async def test_success_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            assert cmd == ["uv", "run", "bandit", "-r", "crackerjack/", "-f", "txt"]
            assert cwd == tmp_path
            return (0, "", "")

        monkeypatch.setattr(security, "_run_command", fake_run_command)

        fixes = await security._run_bandit_analysis(tmp_path)

        assert fixes == ["Bandit security scan completed successfully"]

    async def test_failure_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (1, "", "")

        monkeypatch.setattr(security, "_run_command", fake_run_command)

        fixes = await security._run_bandit_analysis(tmp_path)

        assert fixes == ["Bandit identified security issues for review"]


class TestFixFileSecurityIssues:
    async def test_applies_random_and_debug_print_fixes(self, tmp_path: Path) -> None:
        test_file = tmp_path / "misc.py"
        test_file.write_text(
            'import random\n\nx = random.choice(items)\nprint("password: ", password)\n'
        )

        result = await security._fix_file_security_issues(str(test_file))

        assert result["fixes"] == [f"Applied general security fixes to {test_file}"]
        assert result["files"] == [str(test_file)]
        new_content = test_file.read_text()
        assert "import secrets" in new_content
        assert "secrets.choice(items)" in new_content
        assert "print(" not in new_content

    async def test_nonexistent_file_is_noop(self, tmp_path: Path) -> None:
        result = await security._fix_file_security_issues(str(tmp_path / "missing.py"))

        assert result == {"fixes": [], "files": []}


class TestApplyVulnerabilityFixes:
    async def test_dispatches_to_shell_injection_fixer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        calls: list[Issue] = []

        async def fake_fix_shell_injection(issue: Issue) -> dict[str, list[str]]:
            calls.append(issue)
            return {"fixes": ["Removed shell=True"], "files": []}

        monkeypatch.setattr(security, "_fix_shell_injection", fake_fix_shell_injection)

        issue = _issue(message="shell=True detected")
        fixes, files = await security._apply_vulnerability_fixes(
            "shell_injection", issue, tmp_path, [], []
        )

        assert calls == [issue]
        assert "Removed shell=True" in fixes
        assert files == []

    async def test_unknown_type_is_noop(self, tmp_path: Path) -> None:
        issue = _issue(message="Unknown issue")

        fixes, files = await security._apply_vulnerability_fixes(
            "unknown", issue, tmp_path, [], []
        )

        assert fixes == []
        assert files == []

    async def test_dependency_vulnerability_receives_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        calls: list[Path] = []

        async def fake_fix_dependency_vulnerability(
            issue: Issue, project_root: Path
        ) -> dict[str, list[str]]:
            calls.append(project_root)
            return {"fixes": ["Upgraded pkg"], "files": ["uv.lock"]}

        monkeypatch.setattr(
            security,
            "_fix_dependency_vulnerability",
            fake_fix_dependency_vulnerability,
        )

        issue = _issue(message="CVE-2024-1 found", stage="pip-audit")
        fixes, files = await security._apply_vulnerability_fixes(
            "dependency_vulnerability", issue, tmp_path, [], []
        )

        assert calls == [tmp_path]
        assert "Upgraded pkg" in fixes
        assert files == ["uv.lock"]


class TestApplyAdditionalFixes:
    async def test_runs_bandit_when_no_fixes_applied(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_bandit(project_root: Path) -> list[str]:
            assert project_root == tmp_path
            return ["Bandit suggestion"]

        monkeypatch.setattr(security, "_run_bandit_analysis", fake_bandit)

        issue = _issue(message="Security issue")
        fixes, _files = await security._apply_additional_fixes(
            issue, tmp_path, [], []
        )

        assert "Bandit suggestion" in fixes

    async def test_skips_bandit_when_fixes_already_applied(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        called = False

        async def fake_bandit(project_root: Path) -> list[str]:
            nonlocal called
            called = True
            return ["should not be called"]

        monkeypatch.setattr(security, "_run_bandit_analysis", fake_bandit)

        test_file = tmp_path / "clean.py"
        test_file.write_text("x = 1\n")
        issue = _issue(message="Security issue", file_path=str(test_file))

        fixes, files = await security._apply_additional_fixes(
            issue, tmp_path, ["Previous fix"], []
        )

        assert called is False
        assert fixes == ["Previous fix"]
        assert files == []


class TestFixSecurityIssue:
    async def test_end_to_end_shell_injection_fix(self, tmp_path: Path) -> None:
        test_file = tmp_path / "runner.py"
        test_file.write_text("import subprocess\n\nsubprocess.run(cmd, shell=True)\n")
        issue = _issue(
            message="Bandit B602: shell=True detected",
            file_path=str(test_file),
        )

        result = await security.fix_security_issue(issue, tmp_path)

        assert result.success
        assert result.confidence == 0.95
        assert result.fixes_applied == [
            f"Fixed shell injection vulnerability in {test_file}"
        ]
        assert result.files_modified == [str(test_file)]
        assert test_file.read_text() == (
            "import subprocess\n\nsubprocess.run(cmd.split())\n"
        )

    async def test_no_fixes_applied_returns_recommendations(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_bandit(project_root: Path) -> list[str]:
            return []

        monkeypatch.setattr(security, "_run_bandit_analysis", fake_bandit)

        issue = _issue(message="Unknown security issue")

        result = await security.fix_security_issue(issue, tmp_path)

        assert not result.success
        assert result.confidence == 0.4
        assert len(result.recommendations) > 0

    async def test_error_handling_returns_error_fix_result(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def raise_error(issue: Issue) -> str:
            raise RuntimeError("boom")

        monkeypatch.setattr(security, "_identify_vulnerability_type", raise_error)

        issue = _issue(message="Security issue")

        result = await security.fix_security_issue(issue, tmp_path)

        assert not result.success
        assert result.confidence == 0.0
        assert "Failed to fix" in result.remaining_issues[0]


class TestSecurityRecommendationsAndErrors:
    def test_get_security_recommendations(self) -> None:
        recommendations = security._get_security_recommendations()

        assert len(recommendations) > 0
        assert any("SAFE_PATTERNS" in rec for rec in recommendations)
        assert any("tempfile" in rec for rec in recommendations)
        assert any("shell=True" in rec for rec in recommendations)
        assert any("environment variables" in rec for rec in recommendations)

    def test_create_error_fix_result(self) -> None:
        error = Exception("Test error message")

        result = security._create_error_fix_result(error)

        assert not result.success
        assert result.confidence == 0.0
        assert "Failed to fix" in result.remaining_issues[0]
        assert len(result.recommendations) > 0
        assert any("manual" in rec.lower() for rec in result.recommendations)


class TestCheckNewCodeSecurity:
    async def test_always_returns_true_even_with_danger_patterns(self) -> None:
        """Preserved verbatim: this is a no-op security gate in the
        original -- it never actually rejects anything. See module
        docstring quirk (2)."""
        assert await security._check_new_code_security("password = 'x'") is True
        assert await security._check_new_code_security("safe_code = 1") is True


class TestExecuteFixPlan:
    async def test_applies_single_change(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("def foo():\n    x = 1\n    return x\n")
        plan = FixPlan(
            file_path=str(test_file),
            issue_type="SECURITY",
            risk_level="low",
            validated_by="test",
            rationale="test rationale",
            changes=[
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="    x = 1",
                    new_code="    x = 2",
                    reason="tighten value",
                )
            ],
        )

        result = await security.execute_fix_plan(plan)

        assert result.success
        assert result.confidence == 0.8
        assert result.fixes_applied == ["Change 0: tighten value"]
        assert result.files_modified == [str(test_file)]
        assert test_file.read_text() == "def foo():\n    x = 2\n    return x\n"

    async def test_replaces_all_occurrences_pre_existing_quirk(
        self, tmp_path: Path
    ) -> None:
        """Preserved verbatim: execute_fix_plan uses a whole-file
        str.replace() rather than a line-range slice, so if `old_code`
        appears more than once, every occurrence is replaced -- not just
        the one at `change.line_range`. See module docstring quirk (1)."""
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "def foo():\n    x = 1\n    return x\n\n\n"
            "def bar():\n    x = 1\n    return x\n"
        )
        plan = FixPlan(
            file_path=str(test_file),
            issue_type="SECURITY",
            risk_level="low",
            validated_by="test",
            rationale="test rationale",
            changes=[
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="    x = 1",
                    new_code="    x = 2",
                    reason="tighten value",
                )
            ],
        )

        result = await security.execute_fix_plan(plan)

        assert result.success
        new_content = test_file.read_text()
        assert new_content.count("x = 2") == 2
        assert "x = 1" not in new_content

    async def test_no_changes_returns_failure(self) -> None:
        plan = FixPlan(
            file_path="module.py",
            issue_type="SECURITY",
            risk_level="low",
            validated_by="test",
            rationale="test rationale",
            changes=[],
        )

        result = await security.execute_fix_plan(plan)

        assert not result.success
        assert "Plan has no changes to apply" in result.remaining_issues

    async def test_missing_file_returns_failure(self, tmp_path: Path) -> None:
        plan = FixPlan(
            file_path=str(tmp_path / "missing.py"),
            issue_type="SECURITY",
            risk_level="low",
            validated_by="test",
            rationale="test rationale",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x",
                    new_code="y",
                    reason="test",
                )
            ],
        )

        result = await security.execute_fix_plan(plan)

        assert not result.success
        assert "Could not read file" in result.remaining_issues[0]

    async def test_invalid_line_range_is_reported(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("x = 1\n")
        plan = FixPlan(
            file_path=str(test_file),
            issue_type="SECURITY",
            risk_level="low",
            validated_by="test",
            rationale="test rationale",
            changes=[
                ChangeSpec(
                    line_range=(10, 12),
                    old_code="x",
                    new_code="y",
                    reason="test",
                )
            ],
        )

        result = await security.execute_fix_plan(plan)

        assert not result.success
        assert "Invalid line range" in result.remaining_issues[0]
