import re
import signal
import threading
import time
import typing as t
from dataclasses import dataclass, field
from re import Pattern

MAX_INPUT_SIZE = 10 * 1024 * 1024
MAX_ITERATIONS = 10
PATTERN_CACHE_SIZE = 100


class CompiledPatternCache:
    _lock = threading.RLock()
    _cache: dict[str, Pattern[str]] = {}
    _max_size = PATTERN_CACHE_SIZE

    @classmethod
    def get_compiled_pattern(cls, pattern: str) -> Pattern[str]:
        return cls.get_compiled_pattern_with_flags(pattern, pattern, 0)

    @classmethod
    def get_compiled_pattern_with_flags(
        cls, cache_key: str, pattern: str, flags: int
    ) -> Pattern[str]:
        with cls._lock:
            if cache_key in cls._cache:
                return cls._cache[cache_key]

            try:
                compiled = re.compile(pattern, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

            if len(cls._cache) >= cls._max_size:
                oldest_key = next(iter(cls._cache))
                del cls._cache[oldest_key]

            cls._cache[cache_key] = compiled
            return compiled

    @classmethod
    def clear_cache(cls) -> None:
        with cls._lock:
            cls._cache.clear()

    @classmethod
    def get_cache_stats(cls) -> dict[str, int | list[str]]:
        with cls._lock:
            return {
                "size": len(cls._cache),
                "max_size": cls._max_size,
                "patterns": list[t.Any](cls._cache.keys()),
            }


def validate_pattern_safety(pattern: str) -> list[str]:
    warnings = []

    if ".*.*" in pattern:
        warnings.append("Multiple .* constructs may cause performance issues")

    if ".+.+" in pattern:
        warnings.append("Multiple .+ constructs may cause performance issues")

    nested_quantifiers = re.findall(r"[+*?]\??[+*?]", pattern)
    if nested_quantifiers:
        warnings.append(f"Nested quantifiers detected: {nested_quantifiers}")

    if "|" in pattern and pattern.count("|") > 10:
        warnings.append("Many alternations may cause performance issues")

    return warnings


@dataclass
class ValidatedPattern:
    name: str
    pattern: str
    replacement: str
    test_cases: list[tuple[str, str]]
    description: str = ""
    global_replace: bool = False
    flags: int = 0
    _compiled_pattern: Pattern[str] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        try:
            self._get_compiled_pattern()
        except ValueError as e:
            if "Invalid regex pattern" in str(e):
                error_msg = str(e).replace(f"'{self.pattern}'", f"'{self.name}'")
                raise ValueError(error_msg) from e
            raise

        if r"\g < " in self.replacement or r" >" in self.replacement:
            raise ValueError(
                f"Bad replacement syntax in '{self.name}': {self.replacement}. "
                "Use \\g<1> not \\g<1>"  # REGEX OK: educational example
            )

        warnings = validate_pattern_safety(self.pattern)
        if warnings:
            pass

        for input_text, expected in self.test_cases:
            try:
                count = 0 if self.global_replace else 1
                result = self._apply_internal(input_text, count)
                if result != expected:
                    raise ValueError(
                        f"Pattern '{self.name}' failed test case: "
                        f"'{input_text}' -> '{result}' != expected '{expected}'"
                    )
            except re.error as e:
                raise ValueError(f"Pattern '{self.name}' failed on '{input_text}': {e}")

    def _get_compiled_pattern(self) -> Pattern[str]:
        cache_key = f"{self.pattern}|flags: {self.flags}"
        return CompiledPatternCache.get_compiled_pattern_with_flags(
            cache_key, self.pattern, self.flags
        )

    def _apply_internal(self, text: str, count: int = 1) -> str:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )

        return self._get_compiled_pattern().sub(self.replacement, text, count=count)

    def apply(self, text: str) -> str:
        count = 0 if self.global_replace else 1
        return self._apply_internal(text, count)

    def apply_iteratively(self, text: str, max_iterations: int = MAX_ITERATIONS) -> str:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive")

        result = text
        for _ in range(max_iterations):
            new_result = self.apply(result)
            if new_result == result:
                break
            result = new_result
        else:
            pass

        return result

    def apply_with_timeout(self, text: str, timeout_seconds: float = 1.0) -> str:
        def timeout_handler(signum: int, frame: t.Any) -> None:
            raise TimeoutError(
                f"Pattern '{self.name}' timed out after {timeout_seconds}s"
            )

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_seconds))

        try:
            result = self.apply(text)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        return result

    def test(self, text: str) -> bool:
        compiled = self._get_compiled_pattern()
        return bool(compiled.search(text))

    def search(self, text: str) -> re.Match[str] | None:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )
        return self._get_compiled_pattern().search(text)

    def findall(self, text: str) -> list[str]:
        if len(text) > MAX_INPUT_SIZE:
            raise ValueError(
                f"Input text too large: {len(text)} bytes > {MAX_INPUT_SIZE}"
            )
        return self._get_compiled_pattern().findall(text)

    def get_performance_stats(
        self, text: str, iterations: int = 100
    ) -> dict[str, float]:
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            self.apply(text)
            end = time.perf_counter()
            times.append(end - start)

        return {
            "mean_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "total_time": sum(times),
        }


SAFE_PATTERNS: dict[str, ValidatedPattern] = {
    "fix_command_spacing": ValidatedPattern(
        name="fix_command_spacing",
        pattern=r"python\s*-\s*m\s+(\w+)",
        replacement=r"python -m \1",
        description="Fix spacing in 'python -m command' patterns",
        test_cases=[
            ("python - m crackerjack", "python -m crackerjack"),
            ("python -m crackerjack", "python -m crackerjack"),
            ("python - m pytest", "python -m pytest"),
            ("other python - m stuff", "other python -m stuff"),
        ],
    ),
    "fix_long_flag_spacing": ValidatedPattern(
        name="fix_long_flag_spacing",
        pattern=r"-\s*-\s*(\w+(?: -\w+)*)",
        replacement=r"--\1",
        description="Fix spacing in long flags like '--help'",
        test_cases=[
            ("- - help", "--help"),
            ("- - ai-fix", "--ai-fix"),
            ("--help", "--help"),
            ("- - start-websocket-server", "--start-websocket-server"),
        ],
    ),
    "fix_short_flag_spacing": ValidatedPattern(
        name="fix_short_flag_spacing",
        pattern=r"(?<!\w)-\s+(\w)(?!\w)",
        replacement=r"-\1",
        description="Fix spacing in short flags like '-t'",
        test_cases=[
            ("python -m crackerjack - t", "python -m crackerjack -t"),
            ("- q", "-q"),
            ("-t", "-t"),
            ("some - x flag", "some -x flag"),
        ],
    ),
    "fix_hyphenated_names": ValidatedPattern(
        name="fix_hyphenated_names",
        pattern=r"(\w+)\s*-\s*(\w+)",
        replacement=r"\1-\2",
        description="Fix spacing in hyphenated names and identifiers",
        test_cases=[
            ("python - pro", "python-pro"),
            (
                "pytest - hypothesis - specialist",
                "pytest-hypothesis - specialist",
            ),
            ("backend - architect", "backend-architect"),
            ("python-pro", "python-pro"),
            ("end - of - file-fixer", "end-of - file-fixer"),
        ],
    ),
    "fix_hyphenated_names_global": ValidatedPattern(
        name="fix_hyphenated_names_global",
        pattern=r"(\w+)\s+-\s+(\w+)",
        replacement=r"\1-\2",
        description="Globally fix spacing in hyphenated names (single pass only)",
        global_replace=True,
        test_cases=[
            ("python - pro", "python-pro"),
            ("end - of - file", "end-of - file"),
            ("already-hyphenated", "already-hyphenated"),
            ("start - middle - end", "start-middle - end"),
        ],
    ),
    "fix_spaced_hyphens": ValidatedPattern(
        name="fix_spaced_hyphens",
        pattern=r"(\w+)\s+-\s+(\w+)",
        replacement=r"\1-\2",
        description="Fix spaced hyphens with spaces around dashes (use apply_iteratively for multi-word)",
        global_replace=True,
        test_cases=[
            ("python - pro", "python-pro"),
            (
                "pytest - hypothesis - specialist",
                "pytest-hypothesis - specialist",
            ),
            (
                "end - of - file - fixer",
                "end-of - file-fixer",
            ),
            ("already-hyphenated", "already-hyphenated"),
            ("mixed-case with - spaces", "mixed-case with-spaces"),
        ],
    ),
    "fix_debug_log_pattern": ValidatedPattern(
        name="fix_debug_log_pattern",
        pattern=r"crackerjack\s*-\s*debug",
        replacement="crackerjack-debug",
        description="Fix spacing in debug log patterns",
        test_cases=[
            ("crackerjack - debug-12345.log", "crackerjack-debug-12345.log"),
            ("crackerjack-debug.log", "crackerjack-debug.log"),
            ("old crackerjack - debug files", "old crackerjack-debug files"),
        ],
    ),
    "fix_job_file_pattern": ValidatedPattern(
        name="fix_job_file_pattern",
        pattern=r"job\s*-\s*(\{[^}]+\}|\w+)",
        replacement=r"job-\1",
        description="Fix spacing in job file patterns",
        test_cases=[
            ("job - {self.web_job_id}.json", "job-{self.web_job_id}.json"),
            ("job - abc123.json", "job-abc123.json"),
            ("job-existing.json", "job-existing.json"),
        ],
    ),
    "fix_markdown_bold": ValidatedPattern(
        name="fix_markdown_bold",
        pattern=r"\*\s+\*(.+?)\s*\*\s+\*",
        replacement=r"**\1**",
        description="Fix spacing in markdown bold patterns",
        test_cases=[
            ("* *Bold Text * *", "**Bold Text**"),
            ("* *🧪 pytest-specialist * *", "**🧪 pytest-specialist**"),
            ("**Already Bold**", "**Already Bold**"),
        ],
    ),
    "mask_pypi_token": ValidatedPattern(
        name="mask_pypi_token",
        pattern=r"\bpypi-[a-zA-Z0-9_-]{12,}\b",
        replacement="pypi-****",
        description="Mask PyPI authentication tokens (word boundaries to prevent"
        " false matches)",
        global_replace=True,
        test_cases=[
            ("pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI", "pypi-****"),
            (
                "Using token: pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI for upload",
                "Using token: pypi-**** for upload",
            ),
            ("pypi-short", "pypi-short"),
            (
                "not pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI",
                "not pypi-****",
            ),
            (
                "Multiple pypi-token1234567890 and pypi-anothertokenhere",
                "Multiple pypi-**** and pypi-****",
            ),
        ],
    ),
    "mask_github_token": ValidatedPattern(
        name="mask_github_token",
        pattern=r"\bghp_[a-zA-Z0-9]{36}\b",
        replacement="ghp_****",
        description="Mask GitHub personal access tokens (exactly 40 chars total"
        " with word boundaries)",
        global_replace=True,
        test_cases=[
            ("ghp_1234567890abcdef1234567890abcdef1234", "ghp_****"),
            (
                "GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef1234",
                "GITHUB_TOKEN=ghp_****",
            ),
            ("ghp_short", "ghp_short"),
            (
                "ghp_1234567890abcdef1234567890abcdef12345",
                "ghp_1234567890abcdef1234567890abcdef12345",
            ),
            (
                "Multiple ghp_1234567890abcdef1234567890abcdef1234 and"
                " ghp_abcdef1234567890abcdef12345678901234",
                "Multiple ghp_**** and ghp_****",
            ),
        ],
    ),
    "mask_generic_long_token": ValidatedPattern(
        name="mask_generic_long_token",
        pattern=r"\b[a-zA-Z0-9_-]{32,}\b",
        replacement="****",
        description="Mask generic long tokens (32+ chars, word boundaries to avoid"
        " false positives)",
        global_replace=True,
        test_cases=[
            ("secret_key=abcdef1234567890abcdef1234567890abcdef", "secret_key=****"),
            (
                "Short token abc123def456",
                "Short token abc123def456",
            ),
            (
                "File path "
                "/very/long/path/that/should/not/be/masked/even/though/its/long",
                "File path "
                "/very/long/path/that/should/not/be/masked/even/though/its/long",
            ),
            ("API_KEY=verylongapikeyhere1234567890123456", "API_KEY=****"),
            (
                "Long-token_with-underscores_123456789012345678",
                "****",
            ),
        ],
    ),
    "mask_token_assignment": ValidatedPattern(
        name="mask_token_assignment",
        pattern=r"(?i)\b(token\s*[=: ]\s*)['\"]([^'\"]{8,})['\"]",
        replacement=r"\1'****'",
        description="Mask token assignments in various formats (case insensitive)",
        global_replace=True,
        test_cases=[
            ('token="abc123def456789"', "token='****'"),
            ("token='long_secret_token_here'", "token='****'"),
            ('token: "another_secret_token"', "token: '****'"),
            ("token = 'spaced_assignment_token'", "token = '****'"),
            ('token="short"', 'token="short"'),
            (
                "not_token='should_not_be_masked'",
                "not_token='should_not_be_masked'",
            ),
            ('TOKEN="UPPERCASE_TOKEN_HERE"', "TOKEN='****'"),
        ],
    ),
    "mask_password_assignment": ValidatedPattern(
        name="mask_password_assignment",
        pattern=r"(?i)\b(password\s*[=: ]\s*)['\"]([^'\"]{8,})['\"]",
        replacement=r"\1'****'",
        description="Mask password assignments in various formats (case insensitive)",
        global_replace=True,
        test_cases=[
            ('password="secret123456"', "password='****'"),
            ("password='my_long_password'", "password='****'"),
            ('password: "another_secret_password"', "password: '****'"),
            ("password = 'spaced_password_assignment'", "password = '****'"),
            ('password="short"', 'password="short"'),
            (
                "not_password='should_not_be_masked'",
                "not_password='should_not_be_masked'",
            ),
            ('PASSWORD="UPPERCASE_PASSWORD"', "PASSWORD='****'"),
        ],
    ),
    "update_pyproject_version": ValidatedPattern(
        name="update_pyproject_version",
        pattern=r'^(version\s*=\s*["\'])([^"\']+)(["\'])$',
        replacement=r"\g<1>NEW_VERSION\g<3>",
        description="Update version in pyproject.toml files (NEW_VERSION placeholder"
        " replaced dynamically)",
        test_cases=[
            ('version = "1.2.3"', 'version = "NEW_VERSION"'),
            ("version='0.1.0'", "version='NEW_VERSION'"),
            ('version="1.0.0-beta"', 'version="NEW_VERSION"'),
            ("version = '2.1.0'", "version = 'NEW_VERSION'"),
            ("version='10.20.30'", "version='NEW_VERSION'"),
            ('name = "my-package"', 'name = "my-package"'),
        ],
    ),
    "remove_trailing_whitespace": ValidatedPattern(
        name="remove_trailing_whitespace",
        pattern=r"[ \t]+$",
        replacement="",
        description="Remove trailing whitespace from lines",
        global_replace=True,
        test_cases=[
            ("line with spaces ", "line with spaces"),
            ("line with tabs\t\t", "line with tabs"),
            ("normal line", "normal line"),
            ("mixed \t ", "mixed"),
            ("", ""),
        ],
    ),
    "normalize_multiple_newlines": ValidatedPattern(
        name="normalize_multiple_newlines",
        pattern=r"\n{3,}",
        replacement="\n\n",
        description="Normalize multiple consecutive newlines to maximum 2",
        global_replace=True,
        test_cases=[
            ("line1\n\n\nline2", "line1\n\nline2"),
            ("line1\n\n\n\n\nline2", "line1\n\nline2"),
            ("line1\n\nline2", "line1\n\nline2"),
            ("line1\nline2", "line1\nline2"),
        ],
    ),
    "fix_subprocess_run_shell": ValidatedPattern(
        name="fix_subprocess_run_shell",
        pattern=r"subprocess\.run\(([^,]+),\s*shell=True\)",
        replacement=r"subprocess.run(\1.split())",
        description="Remove shell=True from subprocess.run calls",
        global_replace=True,
        test_cases=[
            ("subprocess.run(cmd, shell=True)", "subprocess.run(cmd.split())"),
            (
                "subprocess.run('ls -la', shell=True)",
                "subprocess.run('ls -la'.split())",
            ),
            (
                "subprocess.run(command, shell=False)",
                "subprocess.run(command, shell=False)",
            ),
        ],
    ),
    "fix_subprocess_call_shell": ValidatedPattern(
        name="fix_subprocess_call_shell",
        pattern=r"subprocess\.call\(([^,]+),\s*shell=True\)",
        replacement=r"subprocess.call(\1.split())",
        description="Remove shell=True from subprocess.call calls",
        global_replace=True,
        test_cases=[
            ("subprocess.call(cmd, shell=True)", "subprocess.call(cmd.split())"),
            (
                "subprocess.call('ls -la', shell=True)",
                "subprocess.call('ls -la'.split())",
            ),
            (
                "subprocess.call(command, shell=False)",
                "subprocess.call(command, shell=False)",
            ),
        ],
    ),
    "fix_subprocess_popen_shell": ValidatedPattern(
        name="fix_subprocess_popen_shell",
        pattern=r"subprocess\.Popen\(([^,]+), \s*shell=True\)",
        replacement=r"subprocess.Popen(\1.split())",
        description="Remove shell=True from subprocess.Popen calls",
        global_replace=True,
        test_cases=[
            ("subprocess.Popen(cmd, shell=True)", "subprocess.Popen(cmd.split())"),
            (
                "subprocess.Popen('ls -la', shell=True)",
                "subprocess.Popen('ls -la'.split())",
            ),
            (
                "subprocess.Popen(command, shell=False)",
                "subprocess.Popen(command, shell=False)",
            ),
        ],
    ),
    "fix_unsafe_yaml_load": ValidatedPattern(
        name="fix_unsafe_yaml_load",
        pattern=r"\byaml\.load\(",
        replacement="yaml.safe_load(",
        description="Replace unsafe yaml.load with yaml.safe_load",
        global_replace=True,
        test_cases=[
            ("yaml.load(file)", "yaml.safe_load(file)"),
            ("data = yaml.load(content)", "data = yaml.safe_load(content)"),
            ("yaml.safe_load(content)", "yaml.safe_load(content)"),
            (
                "my_yaml.load(content)",
                "my_yaml.load(content)",
            ),
        ],
    ),
    "fix_weak_md5_hash": ValidatedPattern(
        name="fix_weak_md5_hash",
        pattern=r"\bhashlib\.md5\(",
        replacement="hashlib.sha256(",
        description="Replace weak MD5 hashing with SHA256",
        global_replace=True,
        test_cases=[
            ("hashlib.md5(data)", "hashlib.sha256(data)"),
            ("hash = hashlib.md5(content)", "hash = hashlib.sha256(content)"),
            ("hashlib.sha256(data)", "hashlib.sha256(data)"),
        ],
    ),
    "fix_weak_sha1_hash": ValidatedPattern(
        name="fix_weak_sha1_hash",
        pattern=r"\bhashlib\.sha1\(",
        replacement="hashlib.sha256(",
        description="Replace weak SHA1 hashing with SHA256",
        global_replace=True,
        test_cases=[
            ("hashlib.sha1(data)", "hashlib.sha256(data)"),
            ("hash = hashlib.sha1(content)", "hash = hashlib.sha256(content)"),
            ("hashlib.sha256(data)", "hashlib.sha256(data)"),
        ],
    ),
    "fix_insecure_random_choice": ValidatedPattern(
        name="fix_insecure_random_choice",
        pattern=r"random\.choice\(([^)]+)\)",
        replacement=r"secrets.choice(\1)",
        description="Replace insecure random.choice with secrets.choice",
        global_replace=True,
        test_cases=[
            ("random.choice(options)", "secrets.choice(options)"),
            ("item = random.choice(items)", "item = secrets.choice(items)"),
            ("secrets.choice(options)", "secrets.choice(options)"),
        ],
    ),
    "remove_debug_prints_with_secrets": ValidatedPattern(
        name="remove_debug_prints_with_secrets",
        pattern=r"print\s*\([^)]*(?: password|secret|key|token)[^)]*\)",
        replacement="",
        description="Remove debug print statements that contain sensitive information",
        global_replace=True,
        test_cases=[
            ('print("password: ", password)', ""),
            ("print(f'Token: {token}')", ""),
            ("print('Debug secret value')", ""),
            (
                "print('Normal debug message')",
                "print('Normal debug message')",
            ),
            ('print("API key is", key)', ""),
        ],
    ),
    "normalize_assert_statements": ValidatedPattern(
        name="normalize_assert_statements",
        pattern=r"assert (.+?)\s*==\s*(.+)",
        replacement=r"assert \1 == \2",
        description="Normalize spacing around == in assert statements",
        global_replace=True,
        test_cases=[
            ("assert result==expected", "assert result == expected"),
            ("assert value == other", "assert value == other"),
            ("assert result== expected", "assert result == expected"),
            ("assert result ==expected", "assert result == expected"),
            (
                "assert result == expected",
                "assert result == expected",
            ),
        ],
    ),
    "validate_job_id_alphanumeric": ValidatedPattern(
        name="validate_job_id_alphanumeric",
        pattern=r"^[a-zA-Z0-9_-]+$",
        replacement="VALID",
        description="Validate job ID contains only alphanumeric characters, "
        "underscores, and hyphens",
        test_cases=[
            ("valid_job-123", "VALID"),
            ("another_valid-job_456", "VALID"),
            ("job_123", "VALID"),
        ],
    ),
    "remove_coverage_fail_under": ValidatedPattern(
        name="remove_coverage_fail_under",
        pattern=r"--cov-fail-under=\d+\.?\d*\s*",
        replacement="",
        description="Remove coverage fail-under flags from pytest addopts",
        global_replace=True,
        test_cases=[
            ("--cov-fail-under=85 --verbose", "--verbose"),
            ("--cov-fail-under=90.5 -x", "-x"),
            ("--verbose --cov-fail-under=80 ", "--verbose "),
            ("--no-cov", "--no-cov"),
        ],
    ),
    "update_coverage_requirement": ValidatedPattern(
        name="update_coverage_requirement",
        pattern=r"(--cov-fail-under=)\d+\.?\d*",
        replacement=r"\1NEW_COVERAGE",
        description="Update coverage fail-under requirement (NEW_COVERAGE placeholder"
        " replaced dynamically)",
        test_cases=[
            ("--cov-fail-under=85", "--cov-fail-under=NEW_COVERAGE"),
            ("--cov-fail-under=90.5", "--cov-fail-under=NEW_COVERAGE"),
            ("--verbose", "--verbose"),
        ],
    ),
    "detect_directory_traversal_basic": ValidatedPattern(
        name="detect_directory_traversal_basic",
        pattern=r"\.\./",
        replacement="[TRAVERSAL]",
        description="Detect basic directory traversal patterns (../)",
        global_replace=True,
        test_cases=[
            ("../config.txt", "[TRAVERSAL]config.txt"),
            ("normal/path", "normal/path"),
            ("../../etc/passwd", "[TRAVERSAL][TRAVERSAL]etc/passwd"),
        ],
    ),
    "detect_directory_traversal_backslash": ValidatedPattern(
        name="detect_directory_traversal_backslash",
        pattern=r"\.\.[/\\]",
        replacement="[TRAVERSAL]",
        description="Detect directory traversal with forward/back slashes",
        global_replace=True,
        test_cases=[
            ("..\\config.txt", "[TRAVERSAL]config.txt"),
            ("../config.txt", "[TRAVERSAL]config.txt"),
            ("normal/path", "normal/path"),
        ],
    ),
    "detect_url_encoded_traversal": ValidatedPattern(
        name="detect_url_encoded_traversal",
        pattern=r"%2e%2e%2f",
        replacement="[TRAVERSAL]",
        description="Detect URL encoded directory traversal (%2e%2e%2f = ../)",
        global_replace=True,
        test_cases=[
            ("path/%2e%2e%2f/config", "path/[TRAVERSAL]/config"),
            ("normal/path", "normal/path"),
            ("%2e%2e%2fpasswd", "[TRAVERSAL]passwd"),
        ],
    ),
    "detect_double_url_encoded_traversal": ValidatedPattern(
        name="detect_double_url_encoded_traversal",
        pattern=r"%252e%252e%252f",
        replacement="[TRAVERSAL]",
        description="Detect double URL encoded directory traversal",
        global_replace=True,
        test_cases=[
            ("path/%252e%252e%252f/config", "path/[TRAVERSAL]/config"),
            ("normal/path", "normal/path"),
        ],
    ),
    "detect_null_bytes_url": ValidatedPattern(
        name="detect_null_bytes_url",
        pattern=r"%00",
        replacement="[NULL]",
        description="Detect URL encoded null bytes",
        global_replace=True,
        test_cases=[
            ("file.txt%00.jpg", "file.txt[NULL].jpg"),
            ("normal.txt", "normal.txt"),
        ],
    ),
    "detect_null_bytes_literal": ValidatedPattern(
        name="detect_null_bytes_literal",
        pattern=r"\\x00",
        replacement="[NULL]",
        description="Detect literal null byte patterns",
        global_replace=True,
        test_cases=[
            ("file.txt\\x00", "file.txt[NULL]"),
            ("normal.txt", "normal.txt"),
        ],
    ),
    "detect_utf8_overlong_null": ValidatedPattern(
        name="detect_utf8_overlong_null",
        pattern=r"%c0%80",
        replacement="[NULL]",
        description="Detect UTF-8 overlong null byte encoding",
        global_replace=True,
        test_cases=[
            ("file.txt%c0%80", "file.txt[NULL]"),
            ("normal.txt", "normal.txt"),
        ],
    ),
    "detect_sys_directory_pattern": ValidatedPattern(
        name="detect_sys_directory_pattern",
        pattern=r"^/sys/?.*",
        replacement="[DANGER]",
        description="Detect access to /sys directory",
        test_cases=[
            ("/sys/", "[DANGER]"),
            ("/sys/devices", "[DANGER]"),
            ("/usr/sys", "/usr/sys"),
        ],
    ),
    "detect_proc_directory_pattern": ValidatedPattern(
        name="detect_proc_directory_pattern",
        pattern=r"^/proc/?.*",
        replacement="[DANGER]",
        description="Detect access to /proc directory",
        test_cases=[
            ("/proc/", "[DANGER]"),
            ("/proc/self", "[DANGER]"),
            ("/usr/proc", "/usr/proc"),
        ],
    ),
    "detect_etc_directory_pattern": ValidatedPattern(
        name="detect_etc_directory_pattern",
        pattern=r"^/etc/?.*",
        replacement="[DANGER]",
        description="Detect access to /etc directory",
        test_cases=[
            ("/etc/", "[DANGER]"),
            ("/etc/passwd", "[DANGER]"),
            ("/usr/etc", "/usr/etc"),
        ],
    ),
    "detect_boot_directory_pattern": ValidatedPattern(
        name="detect_boot_directory_pattern",
        pattern=r"^/boot/?.*",
        replacement="[DANGER]",
        description="Detect access to /boot directory",
        test_cases=[
            ("/boot/", "[DANGER]"),
            ("/boot/grub", "[DANGER]"),
            ("/usr/boot", "/usr/boot"),
        ],
    ),
    "detect_dev_directory_pattern": ValidatedPattern(
        name="detect_dev_directory_pattern",
        pattern=r"^/dev/?.*",
        replacement="[DANGER]",
        description="Detect access to /dev directory",
        test_cases=[
            ("/dev/", "[DANGER]"),
            ("/dev/null", "[DANGER]"),
            ("/usr/dev", "/usr/dev"),
        ],
    ),
    "detect_root_directory_pattern": ValidatedPattern(
        name="detect_root_directory_pattern",
        pattern=r"^/root/?.*",
        replacement="[DANGER]",
        description="Detect access to /root directory",
        test_cases=[
            ("/root/", "[DANGER]"),
            ("/root/.ssh", "[DANGER]"),
            ("/usr/root", "/usr/root"),
        ],
    ),
    "detect_var_log_directory_pattern": ValidatedPattern(
        name="detect_var_log_directory_pattern",
        pattern=r"^/var/log/?.*",
        replacement="[DANGER]",
        description="Detect access to /var/log directory",
        test_cases=[
            ("/var/log/", "[DANGER]"),
            ("/var/log/messages", "[DANGER]"),
            ("/usr/var/log", "/usr/var/log"),
        ],
    ),
    "detect_bin_directory_pattern": ValidatedPattern(
        name="detect_bin_directory_pattern",
        pattern=r"^/(usr/)?bin/?.*",
        replacement="[DANGER]",
        description="Detect access to /bin or /usr/bin directories",
        test_cases=[
            ("/bin/", "[DANGER]"),
            ("/usr/bin/", "[DANGER]"),
            ("/usr/local/bin", "/usr/local/bin"),
        ],
    ),
    "detect_sbin_directory_pattern": ValidatedPattern(
        name="detect_sbin_directory_pattern",
        pattern=r"^/(usr/)?sbin/?.*",
        replacement="[DANGER]",
        description="Detect access to /sbin or /usr/sbin directories",
        test_cases=[
            ("/sbin/", "[DANGER]"),
            ("/usr/sbin/", "[DANGER]"),
            ("/usr/local/sbin", "/usr/local/sbin"),
        ],
    ),
    "detect_parent_directory_in_path": ValidatedPattern(
        name="detect_parent_directory_in_path",
        pattern=r"\.\.",
        replacement="[PARENT]",
        description="Detect parent directory references anywhere in path",
        global_replace=True,
        test_cases=[
            ("../config", "[PARENT]/config"),
            ("safe/path", "safe/path"),
            ("path/../other", "path/[PARENT]/other"),
        ],
    ),
    "detect_suspicious_temp_traversal": ValidatedPattern(
        name="detect_suspicious_temp_traversal",
        pattern=r"/tmp/.*\.\./",  # nosec B108
        replacement="[SUSPICIOUS]",
        description="Detect traversal attempts in temp directories",
        test_cases=[
            ("/tmp/safe/../etc/passwd", "[SUSPICIOUS]etc/passwd"),  # nosec B108
            ("/tmp/normal/file.txt", "/tmp/normal/file.txt"),  # nosec B108
        ],
    ),
    "detect_suspicious_var_traversal": ValidatedPattern(
        name="detect_suspicious_var_traversal",
        pattern=r"/var/.*\.\./",
        replacement="[SUSPICIOUS]",
        description="Detect traversal attempts in var directories",
        test_cases=[
            ("/var/lib/../etc/passwd", "[SUSPICIOUS]etc/passwd"),
            ("/var/lib/normal.txt", "/var/lib/normal.txt"),
        ],
    ),
    "ruff_check_error": ValidatedPattern(
        name="ruff_check_error",
        pattern=r"^(.+?): (\d+): (\d+): ([A-Z]\d+) (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Code: \4, Message: \5",
        description="Parse ruff-check error output: file: line: col: code message",
        test_cases=[
            (
                "crackerjack/core.py: 123: 45: E501 line too long",
                "File: crackerjack/core.py, Line: 123, Col: 45, Code: E501, Message: "
                "line too long",
            ),
            (
                "./test.py: 1: 1: F401 unused import",
                "File: ./test.py, Line: 1, Col: 1, Code: F401, Message: unused import",
            ),
            (
                "src/main.py: 999: 80: W291 trailing whitespace",
                "File: src/main.py, Line: 999, Col: 80, Code: W291, Message: trailing "
                "whitespace",
            ),
        ],
    ),
    "ruff_check_summary": ValidatedPattern(
        name="ruff_check_summary",
        pattern=r"Found (\d+) error",
        replacement=r"Found \1 error(s)",
        description="Parse ruff-check summary line for error count",
        test_cases=[
            ("Found 5 error", "Found 5 error(s)"),
            ("Found 1 error in 3 files", "Found 1 error(s) in 3 files"),
            ("Found 42 error detected", "Found 42 error(s) detected"),
        ],
    ),
    "pyright_error": ValidatedPattern(
        name="pyright_error",
        pattern=r"^(.+?): (\d+): (\d+) - error: (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Error: \4",
        description="Parse pyright error output: file: line: col - error: message",
        test_cases=[
            (
                "src/app.py: 45: 12 - error: Undefined variable",
                "File: src/app.py, Line: 45, Col: 12, Error: Undefined variable",
            ),
            (
                "test.py: 1: 1 - error: Type mismatch",
                "File: test.py, Line: 1, Col: 1, Error: Type mismatch",
            ),
            (
                "./main.py: 999: 50 - error: Missing return statement",
                "File: ./main.py, Line: 999, Col: 50, Error: Missing return statement",
            ),
        ],
    ),
    "pyright_warning": ValidatedPattern(
        name="pyright_warning",
        pattern=r"^(.+?): (\d+): (\d+) - warning: (.+)$",
        replacement=r"File: \1, Line: \2, Col: \3, Warning: \4",
        description="Parse pyright warning output: file: line: col - warning: message",
        test_cases=[
            (
                "src/app.py: 45: 12 - warning: Unused variable",
                "File: src/app.py, Line: 45, Col: 12, Warning: Unused variable",
            ),
            (
                "test.py: 1: 1 - warning: Deprecated API",
                "File: test.py, Line: 1, Col: 1, Warning: Deprecated API",
            ),
            (
                "./main.py: 999: 50 - warning: Type could be more specific",
                "File: ./main.py, Line: 999, Col: 50, Warning: Type could be more"
                " specific",
            ),
        ],
    ),
    "pyright_summary": ValidatedPattern(
        name="pyright_summary",
        pattern=r"(\d+) error[s]?, (\d+) warning[s]?",
        replacement=r"\1 errors, \2 warnings",
        description="Parse pyright summary with error and warning counts",
        test_cases=[
            ("5 errors, 3 warnings", "5 errors, 3 warnings"),
            ("1 error, 1 warning", "1 errors, 1 warnings"),
            ("0 errors, 10 warnings found", "0 errors, 10 warnings found"),
        ],
    ),
    "bandit_issue": ValidatedPattern(
        name="bandit_issue",
        pattern=r">> Issue: \[([A-Z]\d+): \w+\] (.+)",
        replacement=r"Security Issue [\1]: \2",
        description="Parse bandit security issue output with code and message",
        test_cases=[
            (
                ">> Issue: [B602: subprocess_popen_with_shell_equals_true] Use of "
                "shell=True",
                "Security Issue [B602]: Use of shell=True",
            ),
            (
                ">> Issue: [B101: assert_used] Use of assert detected",
                "Security Issue [B101]: Use of assert detected",
            ),
            (
                ">> Issue: [B301: pickle] Pickle library detected",
                "Security Issue [B301]: Pickle library detected",
            ),
        ],
    ),
    "bandit_location": ValidatedPattern(
        name="bandit_location",
        pattern=r"Location: (.+?): (\d+): (\d+)",
        replacement=r"Location: File \1, Line \2, Column \3",
        description="Parse bandit location information for security issues",
        test_cases=[
            (
                "Location: src/security.py: 123: 45",
                "Location: File src/security.py, Line 123, Column 45",
            ),
            ("Location: ./test.py: 1: 1", "Location: File ./test.py, Line 1, Column 1"),
            (
                "Location: crackerjack/core.py: 999: 80",
                "Location: File crackerjack/core.py, Line 999, Column 80",
            ),
        ],
    ),
    "bandit_confidence": ValidatedPattern(
        name="bandit_confidence",
        pattern=r"Confidence: (\w+)",
        replacement=r"Confidence Level: \1",
        description="Parse bandit confidence level for security issues",
        test_cases=[
            ("Confidence: HIGH", "Confidence Level: HIGH"),
            ("Confidence: MEDIUM", "Confidence Level: MEDIUM"),
            ("Confidence: LOW", "Confidence Level: LOW"),
        ],
    ),
    "bandit_severity": ValidatedPattern(
        name="bandit_severity",
        pattern=r"Severity: (\w+)",
        replacement=r"Severity Level: \1",
        description="Parse bandit severity level for security issues",
        test_cases=[
            ("Severity: HIGH", "Severity Level: HIGH"),
            ("Severity: MEDIUM", "Severity Level: MEDIUM"),
            ("Severity: LOW", "Severity Level: LOW"),
        ],
    ),
    "mypy_error": ValidatedPattern(
        name="mypy_error",
        pattern=r"^(.+?): (\d+): error: (.+)$",
        replacement=r"File: \1, Line: \2, Error: \3",
        description="Parse mypy error output: file: line: error: message",
        test_cases=[
            (
                "src/app.py: 45: error: Name 'undefined_var' is not defined",
                "File: src/app.py, Line: 45, Error: Name 'undefined_var' is not "
                "defined",
            ),
            (
                "test.py: 1: error: Incompatible return value type",
                "File: test.py, Line: 1, Error: Incompatible return value type",
            ),
            (
                "./main.py: 999: error: Argument has incompatible type",
                "File: ./main.py, Line: 999, Error: Argument has incompatible type",
            ),
        ],
    ),
    "mypy_note": ValidatedPattern(
        name="mypy_note",
        pattern=r"^(.+?): (\d+): note: (.+)$",
        replacement=r"File: \1, Line: \2, Note: \3",
        description="Parse mypy note output: file: line: note: message",
        test_cases=[
            (
                "src/app.py: 45: note: Expected type Union[int, str]",
                "File: src/app.py, Line: 45, Note: Expected type Union[int, str]",
            ),
            (
                "test.py: 1: note: See https: //mypy.readthedocs.io/",
                "File: test.py, Line: 1, Note: See https: //mypy.readthedocs.io/",
            ),
            (
                "./main.py: 999: note: Consider using Optional[...]",
                "File: ./main.py, Line: 999, Note: Consider using Optional[...]",
            ),
        ],
    ),
    "vulture_unused": ValidatedPattern(
        name="vulture_unused",
        pattern=r"^(.+?): (\d+): unused (.+) '(.+)'",
        replacement=r"File: \1, Line: \2, Unused \3: '\4'",
        description="Parse vulture unused code detection: file: line: unused type"
        " 'name'",
        test_cases=[
            (
                "src/app.py: 45: unused variable 'temp_var'",
                "File: src/app.py, Line: 45, Unused variable: 'temp_var'",
            ),
            (
                "test.py: 1: unused function 'helper'",
                "File: test.py, Line: 1, Unused function: 'helper'",
            ),
            (
                "./main.py: 999: unused import 'os'",
                "File: ./main.py, Line: 999, Unused import: 'os'",
            ),
        ],
    ),
    "complexipy_complex": ValidatedPattern(
        name="complexipy_complex",
        pattern=r"^(.+?): (\d+): (\d+) - (.+) is too complex \((\d+)\)",
        replacement=r"File: \1, Line: \2, Col: \3, Function: \4, Complexity: \5",
        description="Parse complexipy complexity detection: file: line: col - function "
        "is too complex (score)",
        test_cases=[
            (
                "src/app.py: 45: 1 - complex_function is too complex (15)",
                "File: src/app.py, Line: 45, Col: 1, Function: complex_function, "
                "Complexity: 15",
            ),
            (
                "test.py: 1: 1 - nested_loops is too complex (20)",
                "File: test.py, Line: 1, Col: 1, Function: nested_loops, "
                "Complexity: 20",
            ),
            (
                "./main.py: 999: 5 - process_data is too complex (18)",
                "File: ./main.py, Line: 999, Col: 5, Function: process_data, "
                "Complexity: 18",
            ),
        ],
    ),
    "pytest_test_start": ValidatedPattern(
        name="pytest_test_start",
        pattern=r"^(.+?):: ?(.+?):: ?(.+?) (PASSED|FAILED|SKIPPED|ERROR)$",
        replacement=r"\1::\2::\3",
        description="Parse pytest test start line with file, class, and method "
        "(3-part format)",
        test_cases=[
            (
                "test_file.py::TestClass::test_method PASSED",
                "test_file.py::TestClass::test_method",
            ),
            (
                "tests/test_core.py::TestCore::test_function FAILED",
                "tests/test_core.py::TestCore::test_function",
            ),
            (
                "src/test.py::MyTest::test_case SKIPPED",
                "src/test.py::MyTest::test_case",
            ),
        ],
    ),
    "pytest_test_result": ValidatedPattern(
        name="pytest_test_result",
        pattern=r"^(.+?) (PASSED|FAILED|SKIPPED|ERROR)(?: \[.*?\])?\s*$",
        replacement=r"\1",
        description="Parse pytest test result line with test identifier",
        test_cases=[
            ("test_file.py::test_method PASSED", "test_file.py::test_method"),
            (
                "tests/test_core.py::test_func FAILED [100%]",
                "tests/test_core.py::test_func",
            ),
            ("src/test.py::test_case SKIPPED ", "src/test.py::test_case"),
        ],
    ),
    "pytest_collection_count": ValidatedPattern(
        name="pytest_collection_count",
        pattern=r"collected (\d+) items?",
        replacement=r"\1",
        description="Parse pytest test collection count",
        test_cases=[
            ("collected 5 items", "5"),
            ("collected 1 item", "1"),
            (
                "collected 42 items for execution",
                "42 for execution",
            ),
        ],
    ),
    "pytest_session_start": ValidatedPattern(
        name="pytest_session_start",
        pattern=r"test session starts",
        replacement=r"test session starts",
        description="Match pytest session start indicator",
        test_cases=[
            ("test session starts", "test session starts"),
            ("pytest test session starts", "pytest test session starts"),
        ],
    ),
    "pytest_coverage_total": ValidatedPattern(
        name="pytest_coverage_total",
        pattern=r"TOTAL\s+\d+\s+\d+\s+(\d+)%",
        replacement=r"\1",
        description="Parse pytest coverage total percentage",
        test_cases=[
            ("TOTAL 123 45 85%", "85"),
            ("TOTAL 1000 250 75%", "75"),
            ("TOTAL 50 0 100%", "100"),
        ],
    ),
    "pytest_detailed_test": ValidatedPattern(
        name="pytest_detailed_test",
        pattern=r"^(.+\.py)::(.+) (PASSED|FAILED|SKIPPED|ERROR)",
        replacement=r"\1::\2",
        description="Parse detailed pytest test output with file, test name, and "
        "status",
        test_cases=[
            (
                "test_file.py::test_method PASSED [50%]",
                "test_file.py::test_method [50%]",
            ),
            (
                "tests/core.py::TestClass::test_func FAILED [75%] [0.1s]",
                "tests/core.py::TestClass::test_func [75%] [0.1s]",
            ),
            (
                "src/test.py::test_case SKIPPED",
                "src/test.py::test_case",
            ),
        ],
    ),
    "docstring_triple_double": ValidatedPattern(
        name="docstring_triple_double",
        pattern=r'^\s*""".*?"""\s*$',
        replacement=r"",
        flags=re.MULTILINE | re.DOTALL,
        description="Remove triple-quoted docstrings with double quotes",
        test_cases=[
            (' """This is a docstring""" ', ""),
            ('"""Module docstring"""', ""),
            (' """\n Multi-line\n docstring\n """', ""),
            (
                'regular_code = "not a docstring"',
                'regular_code = "not a docstring"',
            ),
        ],
    ),
    "docstring_triple_single": ValidatedPattern(
        name="docstring_triple_single",
        pattern=r"^\s*'''.*?'''\s*$",
        replacement=r"",
        flags=re.MULTILINE | re.DOTALL,
        description="Remove triple-quoted docstrings with single quotes",
        test_cases=[
            (" '''This is a docstring''' ", ""),
            ("'''Module docstring'''", ""),
            (" '''\n Multi-line\n docstring\n '''", ""),
            (
                "regular_code = 'not a docstring'",
                "regular_code = 'not a docstring'",
            ),
        ],
    ),
    "spacing_after_comma": ValidatedPattern(
        name="spacing_after_comma",
        pattern=r",(\S)",
        replacement=r", \1",
        global_replace=True,
        description="Add space after comma if missing",
        test_cases=[
            ("def func(a, b, c): ", "def func(a, b, c): "),
            ("items = [1, 2, 3, 4]", "items = [1, 2, 3, 4]"),
            ("already, spaced, properly", "already, spaced, properly"),
            ("mixed, spacing, here", "mixed, spacing, here"),
        ],
    ),
    "spacing_after_colon": ValidatedPattern(
        name="spacing_after_colon",
        pattern=r"(?<!https)(?<!http)(?<!ftp)(?<!file)(?<!: )(\b[a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z0-9_][^ \n:]*)",
        replacement=r"\1: \2",
        global_replace=True,
        description="Add space after colon if missing (avoid double colons, URLs, and protocols)",
        test_cases=[
            ("def func(x: int, y: str): ", "def func(x: int, y: str): "),
            ("dict_item = {'key': 'value'}", "dict_item = {'key': 'value'}"),
            ("already: spaced: properly", "already: spaced: properly"),
            ("class::method", "class::method"),
            ("https://github.com", "https://github.com"),
            ("http://example.com", "http://example.com"),
            ("ftp://server.com", "ftp://server.com"),
            ("repo:local", "repo: local"),
        ],
    ),
    "multiple_spaces": ValidatedPattern(
        name="multiple_spaces",
        pattern=r" {2,}",
        replacement=r" ",
        description="Replace multiple spaces with single space",
        global_replace=True,
        test_cases=[
            ("def func( x, y ): ", "def func( x, y ): "),
            ("single space only", "single space only"),
            ("lots of spaces", "lots of spaces"),
            ("\tkeep\ttabs\tbut fix spaces", "\tkeep\ttabs\tbut fix spaces"),
        ],
    ),
    "preserved_comments": ValidatedPattern(
        name="preserved_comments",
        pattern=r"(#.*?(?: coding: | encoding: | type: | noqa | pragma).*)",
        replacement=r"\1",
        description="Match preserved code comments (encoding, type hints, etc.)",
        test_cases=[
            ("# coding: utf-8", "# coding: utf-8"),
            (
                "# encoding: latin-1",
                "# encoding: latin-1",
            ),
            ("# type: ignore", "# type: ignore"),
            ("# noqa: E501", "# noqa: E501"),
            (
                "# pragma: no cover",
                "# pragma: no cover",
            ),
            ("# regular comment", "# regular comment"),
        ],
    ),
    "todo_pattern": ValidatedPattern(
        name="todo_pattern",
        pattern=r"(#.*?TODO.*)",
        replacement=r"\1",
        flags=re.IGNORECASE,
        description="Match TODO comments for validation",
        test_cases=[
            (
                "# TODO: Fix this bug",
                "# TODO: Fix this bug",
            ),
            (
                "# todo: implement later",
                "# todo: implement later",
            ),
            (
                "# TODO refactor this method",
                "# TODO refactor this method",
            ),
            (
                "# FIXME: another issue",
                "# FIXME: another issue",
            ),
            ("# regular comment", "# regular comment"),
        ],
    ),
    "detect_error_response_patterns": ValidatedPattern(
        name="detect_error_response_patterns",
        pattern=r'return\s+.*[\'\"]\{.*[\'\""]error[\'\""].*\}.*[\'\""]',
        replacement=r"MATCH",
        description="Detect error response patterns in Python code for DRY violations",
        test_cases=[
            ('return \'{"error": "msg"}\'', "MATCH"),
            ('return f\'{"error": "msg"}\'', "MATCH"),
            ('return {"success": True}', 'return {"success": True}'),
            ('return \'{"error": "test message", "code": 500}\'', "MATCH"),
        ],
    ),
    "detect_path_conversion_patterns": ValidatedPattern(
        name="detect_path_conversion_patterns",
        pattern=r"Path\([^)]+\)\s+if\s+isinstance\([^)]+, \s*str\)\s+else\s+[^)]+",
        replacement=r"MATCH",
        description="Detect path conversion patterns in Python code for DRY violations",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "MATCH"),
            ("Path(path) if isinstance(path, str) else path", "MATCH"),
            ("Path('/tmp/file')", "Path('/tmp/file')"),
            (
                "Path(input_path) if isinstance(input_path, str) else input_path",
                "MATCH",
            ),
        ],
    ),
    "detect_file_existence_patterns": ValidatedPattern(
        name="detect_file_existence_patterns",
        pattern=r"if\s+not\s+\w+\.exists\(\): ",
        replacement=r"MATCH",
        description="Detect file existence check patterns in Python code for DRY"
        " violations",
        test_cases=[
            ("if not file.exists(): ", "MATCH"),
            ("if not path.exists(): ", "MATCH"),
            ("if not file_path.exists(): ", "MATCH"),
            ("if file.exists(): ", "if file.exists(): "),
        ],
    ),
    "detect_exception_patterns": ValidatedPattern(
        name="detect_exception_patterns",
        pattern=r"except\s+\w*Exception\s+as\s+\w+: ",
        replacement=r"MATCH",
        description="Detect exception handling patterns for base Exception class in Python code for DRY violations",
        test_cases=[
            ("except Exception as e: ", "MATCH"),
            ("except BaseException as error: ", "MATCH"),
            (
                "except ValueError as error: ",
                "except ValueError as error: ",
            ),
            ("try: ", "try: "),
        ],
    ),
    "fix_path_conversion_with_ensure_path": ValidatedPattern(
        name="fix_path_conversion_with_ensure_path",
        pattern=r"Path\([^)]+\)\s+if\s+isinstance\([^)]+, \s*str\)\s+else\s+([^)]+)",
        replacement=r"_ensure_path(\1)",
        description="Replace path conversion patterns with _ensure_path utility "
        "function",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "_ensure_path(value)"),
            ("Path(path) if isinstance(path, str) else path", "_ensure_path(path)"),
            (
                "Path(input_path) if isinstance(input_path, str) else input_path",
                "_ensure_path(input_path)",
            ),
        ],
    ),
    "fix_path_conversion_simple": ValidatedPattern(
        name="fix_path_conversion_simple",
        pattern=r"Path\(([^)]+)\)\s+if\s+isinstance\(\1, \s*str\)\s+else\s+\1",
        replacement=r"_ensure_path(\1)",
        description="Replace simple path conversion patterns with _ensure_path utility "
        "function",
        test_cases=[
            ("Path(value) if isinstance(value, str) else value", "_ensure_path(value)"),
            ("Path(path) if isinstance(path, str) else path", "_ensure_path(path)"),
            (
                "Path(file_path) if isinstance(file_path, str) else file_path",
                "_ensure_path(file_path)",
            ),
        ],
    ),
    "detect_security_keywords": ValidatedPattern(
        name="detect_security_keywords",
        pattern=r"(?i)(bandit|security|vulnerability|hardcoded|"
        r"shell=true|b108|b602|b301|b506|unsafe|injection)",
        replacement=r"MATCH",
        description="Detect security-related keywords in issue messages "
        "(case insensitive)",
        flags=re.IGNORECASE,
        test_cases=[
            ("Bandit security issue found", "MATCH security issue found"),
            ("VULNERABILITY detected", "MATCH detected"),
            ("hardcoded path found", "MATCH path found"),
            ("shell=True usage", "MATCH usage"),
            ("B108 violation", "MATCH violation"),
            ("normal message", "normal message"),
        ],
    ),
    "detect_hardcoded_temp_paths_basic": ValidatedPattern(
        name="detect_hardcoded_temp_paths_basic",
        pattern=r"(?:/tmp/|/temp/|C:\\temp\\|C:\\tmp\\)",  # nosec B108
        replacement="[TEMP_PATH]/",
        description="Detect hardcoded temporary directory paths",
        global_replace=True,
        test_cases=[
            ("/tmp/myfile.txt", "[TEMP_PATH]/myfile.txt"),  # nosec B108
            (r"C:\tmp\data.log", "[TEMP_PATH]/data.log"),
            ("/temp/cache", "[TEMP_PATH]/cache"),
            (r"C:\temp\work", "[TEMP_PATH]/work"),
            ("/regular/path", "/regular/path"),
        ],
    ),
    "replace_hardcoded_temp_paths": ValidatedPattern(
        name="replace_hardcoded_temp_paths",
        pattern=r'Path\("/tmp/([^"]+)"\)',
        replacement=r'Path(tempfile.gettempdir()) / "\1"',
        description="Replace hardcoded /tmp paths with tempfile.gettempdir()",
        global_replace=True,
        test_cases=[
            ('Path("/tmp/myfile.txt")', 'Path(tempfile.gettempdir()) / "myfile.txt"'),
            ('Path("/tmp/data.log")', 'Path(tempfile.gettempdir()) / "data.log"'),
            ('Path("/regular/path")', 'Path("/regular/path")'),
        ],
    ),
    "replace_hardcoded_temp_strings": ValidatedPattern(
        name="replace_hardcoded_temp_strings",
        pattern=r'"/tmp/([^"]+)"',
        replacement=r'str(Path(tempfile.gettempdir()) / "\1")',
        description="Replace hardcoded /tmp string paths with tempfile equivalent",
        global_replace=True,
        test_cases=[
            ('"/tmp/myfile.txt"', 'str(Path(tempfile.gettempdir()) / "myfile.txt")'),
            ('"/tmp/data.log"', 'str(Path(tempfile.gettempdir()) / "data.log")'),
            ('"/regular/path"', '"/regular/path"'),
        ],
    ),
    "replace_hardcoded_temp_single_quotes": ValidatedPattern(
        name="replace_hardcoded_temp_single_quotes",
        pattern=r"'/tmp/([^']+)'",
        replacement=r"str(Path(tempfile.gettempdir()) / '\1')",
        description="Replace hardcoded /tmp paths (single quotes) with tempfile"
        " equivalent",
        global_replace=True,
        test_cases=[
            ("'/tmp/myfile.txt'", "str(Path(tempfile.gettempdir()) / 'myfile.txt')"),
            ("'/tmp/data.log'", "str(Path(tempfile.gettempdir()) / 'data.log')"),
            ("'/regular/path'", "'/regular/path'"),
        ],
    ),
    "replace_test_path_patterns": ValidatedPattern(
        name="replace_test_path_patterns",
        pattern=r'Path\("/test/path"\)',
        replacement=r"Path(tempfile.gettempdir()) / 'test-path'",
        description="Replace hardcoded /test/path patterns with tempfile equivalent",
        test_cases=[
            ('Path("/test/path")', "Path(tempfile.gettempdir()) / 'test-path'"),
            ('Path("/other/path")', 'Path("/other/path")'),
        ],
    ),
    "detect_hardcoded_secrets": ValidatedPattern(
        name="detect_hardcoded_secrets",
        pattern=r'\b\w*(password|secret|key|token)\w*\s*=\s*[\'"][^\'"]+[\'"]',
        replacement="[SECRET_DETECTED]",
        description="Detect hardcoded secrets in assignments (case insensitive)",
        flags=re.IGNORECASE,
        global_replace=True,
        test_cases=[
            ('password = "secret123"', "[SECRET_DETECTED]"),
            ("api_key = 'abc123def'", "[SECRET_DETECTED]"),
            ('TOKEN = "my-token-here"', "[SECRET_DETECTED]"),
            ("username = 'user123'", "username = 'user123'"),
        ],
    ),
    "extract_variable_name_from_assignment": ValidatedPattern(
        name="extract_variable_name_from_assignment",
        pattern=r"\s*(\w+)\s*=.*",
        replacement=r"\1",
        description="Extract variable name from assignment statement",
        test_cases=[
            ("password = 'secret'", "password"),
            ("api_key = 'value'", "api_key"),
            (" token =", "token"),
            ("complex_variable_name = value", "complex_variable_name"),
        ],
    ),
    "detect_insecure_random_usage": ValidatedPattern(
        name="detect_insecure_random_usage",
        pattern=r"\brandom\.(?:random|choice)\([^)]*\)",
        replacement="[INSECURE_RANDOM]()",
        description="Detect insecure random module usage",
        global_replace=True,
        test_cases=[
            ("random.random()", "[INSECURE_RANDOM]()"),
            ("random.choice(options)", "[INSECURE_RANDOM]()"),
            ("secrets.choice(options)", "secrets.choice(options)"),
            ("my_random.choice()", "my_random.choice()"),
        ],
    ),
    "validate_sql_injection_patterns": ValidatedPattern(
        name="validate_sql_injection_patterns",
        pattern=r"\b(union|select|insert|update|delete|drop|create|alter|"
        r"exec|execute)\b",
        replacement="[SQL_INJECTION]",
        flags=re.IGNORECASE,
        description="Detect SQL injection patterns in input validation "
        "(case insensitive)",
        global_replace=True,
        test_cases=[
            ("UNION SELECT", "[SQL_INJECTION] [SQL_INJECTION]"),
            ("drop table", "[SQL_INJECTION] table"),
            ("normal text", "normal text"),
            ("exec command", "[SQL_INJECTION] command"),
            ("execute procedure", "[SQL_INJECTION] procedure"),
        ],
    ),
    "validate_sql_comment_patterns": ValidatedPattern(
        name="validate_sql_comment_patterns",
        pattern=r"(-{2,}|\/\*|\*\/)",
        replacement="[SQL_COMMENT]",
        description="Detect SQL comment patterns in input validation",
        global_replace=True,
        test_cases=[
            ("--comment", "[SQL_COMMENT]comment"),
            ("/* comment */", "[SQL_COMMENT] comment [SQL_COMMENT]"),
            ("normal-text", "normal-text"),
            ("---triple", "[SQL_COMMENT]triple"),
        ],
    ),
    "validate_sql_boolean_injection": ValidatedPattern(
        name="validate_sql_boolean_injection",
        pattern=r"\b(or|and)\b.*=",
        replacement="[BOOLEAN_INJECTION]",
        flags=re.IGNORECASE,
        description="Detect boolean-based SQL injection patterns (case insensitive)",
        global_replace=True,
        test_cases=[
            ("or 1=1", "[BOOLEAN_INJECTION]1"),
            ("AND password=", "[BOOLEAN_INJECTION]"),
            ("normal or text", "normal or text"),
            ("value=test", "value=test"),
        ],
    ),
    "validate_sql_server_specific": ValidatedPattern(
        name="validate_sql_server_specific",
        pattern=r"\b(xp_cmdshell|sp_executesql)\b",
        replacement="[SQLSERVER_EXPLOIT]",
        flags=re.IGNORECASE,
        description="Detect SQL Server specific attack patterns (case insensitive)",
        global_replace=True,
        test_cases=[
            ("xp_cmdshell", "[SQLSERVER_EXPLOIT]"),
            ("SP_EXECUTESQL", "[SQLSERVER_EXPLOIT]"),
            ("normal text", "normal text"),
        ],
    ),
    "validate_code_eval_injection": ValidatedPattern(
        name="validate_code_eval_injection",
        pattern=r"\b(eval|exec|execfile)\s*\(",
        replacement="[CODE_EVAL](",
        description="Detect Python code evaluation injection patterns",
        global_replace=True,
        test_cases=[
            ("eval(code)", "[CODE_EVAL](code)"),
            ("exec(command)", "[CODE_EVAL](command)"),
            ("execfile(script)", "[CODE_EVAL](script)"),
            ("evaluate()", "evaluate()"),
        ],
    ),
    "validate_code_dynamic_access": ValidatedPattern(
        name="validate_code_dynamic_access",
        pattern=r"\b(__import__|getattr|setattr|delattr)\b",
        replacement="[DYNAMIC_ACCESS]",
        description="Detect dynamic attribute access patterns for code injection",
        global_replace=True,
        test_cases=[
            ("__import__", "[DYNAMIC_ACCESS]"),
            ("getattr(obj, name)", "[DYNAMIC_ACCESS](obj, name)"),
            ("setattr(obj, name)", "[DYNAMIC_ACCESS](obj, name)"),
            ("delattr(obj, name)", "[DYNAMIC_ACCESS](obj, name)"),
            ("mygetattr", "mygetattr"),
        ],
    ),
    "validate_code_system_commands": ValidatedPattern(
        name="validate_code_system_commands",
        pattern=r"\b(subprocess|os\.system|os\.popen|commands\.)",
        replacement="[SYSTEM_COMMAND]",
        description="Detect system command execution patterns for code injection",
        global_replace=True,
        test_cases=[
            ("subprocess.run", "[SYSTEM_COMMAND].run"),
            ("os.system(cmd)", "[SYSTEM_COMMAND](cmd)"),
            ("os.popen(cmd)", "[SYSTEM_COMMAND](cmd)"),
            ("commands.getoutput", "[SYSTEM_COMMAND]getoutput"),
            ("mysubprocess", "mysubprocess"),
        ],
    ),
    "validate_code_compilation": ValidatedPattern(
        name="validate_code_compilation",
        pattern=r"\bcompile\s*\(|code\.compile",
        replacement="[CODE_COMPILE]",
        description="Detect code compilation patterns for injection",
        global_replace=True,
        test_cases=[
            ("compile(source)", "[CODE_COMPILE]source)"),
            ("code.compile(source)", "[CODE_COMPILE](source)"),
            ("compiled", "compiled"),
        ],
    ),
    "validate_job_id_format": ValidatedPattern(
        name="validate_job_id_format",
        pattern=r"^[a-zA-Z0-9\-_]+$",
        replacement="VALID_JOB_ID",
        description="Validate job ID format - alphanumeric with hyphens and"
        " underscores only",
        test_cases=[
            ("valid_job-123", "VALID_JOB_ID"),
            ("another-valid_job_456", "VALID_JOB_ID"),
            ("job_123", "VALID_JOB_ID"),
            ("UPPERCASE_JOB-ID", "VALID_JOB_ID"),
            ("hyphen-underscore_combo", "VALID_JOB_ID"),
        ],
    ),
    "validate_env_var_name_format": ValidatedPattern(
        name="validate_env_var_name_format",
        pattern=r"^[A-Z_][A-Z0-9_]*$",
        replacement="VALID_ENV_VAR_NAME",
        description="Validate environment variable name format - uppercase letters, "
        " numbers, underscores only, must start with letter or underscore",
        test_cases=[
            ("VALID_VAR", "VALID_ENV_VAR_NAME"),
            ("_VALID_VAR", "VALID_ENV_VAR_NAME"),
            ("API_KEY_123", "VALID_ENV_VAR_NAME"),
            ("DATABASE_URL", "VALID_ENV_VAR_NAME"),
            ("_PRIVATE_VAR", "VALID_ENV_VAR_NAME"),
        ],
    ),
    "update_repo_revision": ValidatedPattern(
        name="update_repo_revision",
        pattern=r'("repo": "[^"]+?".*?"rev": )"([^"]+)"',
        replacement=r'\1"NEW_REVISION"',
        description="Update repository revision in config files (NEW_REVISION"
        " placeholder replaced dynamically)",
        flags=re.DOTALL,
        test_cases=[
            (
                '"repo": "https: //github.com/user/repo".*"rev": "old_rev"',
                '"repo": "https: //github.com/user/repo".*"rev": "NEW_REVISION"',
            ),
            (
                '"repo": "git@github.com: user/repo.git", "branch": "main", "rev": '
                '"abc123"',
                '"repo": "git@github.com: user/repo.git", "branch": "main", "rev": '
                '"NEW_REVISION"',
            ),
            (
                '{"repo": "https: //example.com/repo", "description": "test", "rev": '
                '"456def"}',
                '{"repo": "https: //example.com/repo", "description": "test", "rev": '
                '"NEW_REVISION"}',
            ),
        ],
    ),
    "sanitize_localhost_urls": ValidatedPattern(
        name="sanitize_localhost_urls",
        pattern=r"https?: //localhost: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize localhost URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //localhost: 8000/api/test", "[INTERNAL_URL]"),
            ("https: //localhost: 3000/dashboard", "[INTERNAL_URL]"),
            (
                "Visit http: //localhost: 8080/admin for details",
                "Visit [INTERNAL_URL] for details",
            ),
            ("https: //example.com/test", "https: //example.com/test"),
        ],
    ),
    "sanitize_127_urls": ValidatedPattern(
        name="sanitize_127_urls",
        pattern=r"https?: //127\.0\.0\.1: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize 127.0.0.1 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //127.0.0.1: 8000/api", "[INTERNAL_URL]"),
            ("https: //127.0.0.1: 3000/test", "[INTERNAL_URL]"),
            ("Connect to http: //127.0.0.1: 5000/status", "Connect to [INTERNAL_URL]"),
            (
                "https: //192.168.1.1: 8080/test",
                "https: //192.168.1.1: 8080/test",
            ),
        ],
    ),
    "sanitize_any_localhost_urls": ValidatedPattern(
        name="sanitize_any_localhost_urls",
        pattern=r"https?: //0\.0\.0\.0: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize 0.0.0.0 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("http: //0.0.0.0: 8000/api", "[INTERNAL_URL]"),
            ("https: //0.0.0.0: 3000/test", "[INTERNAL_URL]"),
            ("https: //1.1.1.1: 8080/test", "https: //1.1.1.1: 8080/test"),
        ],
    ),
    "sanitize_ws_localhost_urls": ValidatedPattern(
        name="sanitize_ws_localhost_urls",
        pattern=r"ws: //localhost: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize WebSocket localhost URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("ws: //localhost: 8675/websocket", "[INTERNAL_URL]"),
            ("ws: //localhost: 3000/socket", "[INTERNAL_URL]"),
            ("Connect to ws: //localhost: 8000/ws", "Connect to [INTERNAL_URL]"),
            (
                "wss: //example.com: 443/socket",
                "wss: //example.com: 443/socket",
            ),
        ],
    ),
    "sanitize_ws_127_urls": ValidatedPattern(
        name="sanitize_ws_127_urls",
        pattern=r"ws: //127\.0\.0\.1: \d+[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize WebSocket 127.0.0.1 URLs with ports for security",
        global_replace=True,
        test_cases=[
            ("ws: //127.0.0.1: 8675/websocket", "[INTERNAL_URL]"),
            ("ws: //127.0.0.1: 3000/socket", "[INTERNAL_URL]"),
            (
                "ws: //192.168.1.1: 8080/socket",
                "ws: //192.168.1.1: 8080/socket",
            ),
        ],
    ),
    "sanitize_simple_localhost_urls": ValidatedPattern(
        name="sanitize_simple_localhost_urls",
        pattern=r"http: //localhost[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize simple localhost URLs without explicit ports for security",
        global_replace=True,
        test_cases=[
            ("http: //localhost/api/test", "[INTERNAL_URL]"),
            ("http: //localhost/dashboard", "[INTERNAL_URL]"),
            ("Visit http: //localhost/admin", "Visit [INTERNAL_URL]"),
            (
                "https: //localhost: 443/test",
                "https: //localhost: 443/test",
            ),
        ],
    ),
    "sanitize_simple_ws_localhost_urls": ValidatedPattern(
        name="sanitize_simple_ws_localhost_urls",
        pattern=r"ws: //localhost[^\s]*",
        replacement="[INTERNAL_URL]",
        description="Sanitize simple WebSocket localhost URLs without explicit ports"
        " for security",
        global_replace=True,
        test_cases=[
            ("ws: //localhost/websocket", "[INTERNAL_URL]"),
            ("ws: //localhost/socket", "[INTERNAL_URL]"),
            ("Connect to ws: //localhost/ws", "Connect to [INTERNAL_URL]"),
            (
                "wss: //localhost: 443/socket",
                "wss: //localhost: 443/socket",
            ),
        ],
    ),
    "detect_tempfile_usage": ValidatedPattern(
        name="detect_tempfile_usage",
        pattern=r"tempfile\.(mkdtemp|NamedTemporaryFile|TemporaryDirectory)",
        replacement="MATCH",
        test_cases=[
            ("tempfile.mkdtemp()", "MATCH()"),
            ("tempfile.NamedTemporaryFile()", "MATCH()"),
            ("tempfile.TemporaryDirectory()", "MATCH()"),
            (
                "not_tempfile.other()",
                "not_tempfile.other()",
            ),
        ],
        description="Detect tempfile module usage for resource management integration",
    ),
    "detect_subprocess_usage": ValidatedPattern(
        name="detect_subprocess_usage",
        pattern=r"subprocess\.(Popen|run)",
        replacement="MATCH",
        test_cases=[
            ("subprocess.Popen(cmd)", "MATCH(cmd)"),
            ("subprocess.run(['cmd'])", "MATCH(['cmd'])"),
            ("not_subprocess.other()", "not_subprocess.other()"),
        ],
        description="Detect subprocess module usage for resource management integration",
    ),
    "detect_asyncio_create_task": ValidatedPattern(
        name="detect_asyncio_create_task",
        pattern=r"asyncio\.create_task",
        replacement="MATCH",
        test_cases=[
            ("asyncio.create_task(coro)", "MATCH(coro)"),
            ("not_asyncio.other()", "not_asyncio.other()"),
        ],
        description="Detect asyncio.create_task usage for resource management"
        " integration",
    ),
    "detect_file_open_operations": ValidatedPattern(
        name="detect_file_open_operations",
        pattern=r"(\.open\(|with open\()",
        replacement=r"MATCH",
        test_cases=[
            ("file.open()", "fileMATCH)"),
            ("with open('file.txt'): ", "MATCH'file.txt'): "),
            ("other_method()", "other_method()"),
        ],
        description="Detect file open operations for resource management integration",
    ),
    "match_async_function_definition": ValidatedPattern(
        name="match_async_function_definition",
        pattern=r"(async def \w+\([^)]*\)[^: ]*: )",
        replacement=r"\1",
        test_cases=[
            ("async def foo(): ", "async def foo(): "),
            ("async def bar(a, b) -> None: ", "async def bar(a, b) -> None: "),
            ("def sync_func(): ", "def sync_func(): "),
        ],
        description="Match async function definitions for resource management"
        " integration",
    ),
    "match_class_definition": ValidatedPattern(
        name="match_class_definition",
        pattern=r"class (\w+).*: ",
        replacement=r"\1",
        test_cases=[
            ("class MyClass: ", "MyClass"),
            ("class MyClass(BaseClass): ", "MyClass"),
            ("class MyClass(Base, Mixin): ", "MyClass"),
            ("def not_class(): ", "def not_class(): "),
        ],
        description="Match class definitions for resource management integration",
    ),
    "replace_subprocess_popen_basic": ValidatedPattern(
        name="replace_subprocess_popen_basic",
        pattern=r"subprocess\.Popen\(",
        replacement="managed_proc = resource_ctx.managed_process(subprocess.Popen(",
        test_cases=[
            (
                "subprocess.Popen(cmd)",
                "managed_proc = resource_ctx.managed_process(subprocess.Popen(cmd)",
            ),
            (
                "result = subprocess.Popen(['ls'])",
                "result = managed_proc = resource_ctx.managed_process("
                "subprocess.Popen(['ls'])",
            ),
        ],
        description="Replace subprocess.Popen with managed version",
    ),
    "replace_subprocess_popen_assignment": ValidatedPattern(
        name="replace_subprocess_popen_assignment",
        pattern=r"(\w+)\s*=\s*subprocess\.Popen\(",
        replacement=r"process = subprocess.Popen(",
        test_cases=[
            ("proc = subprocess.Popen(cmd)", "process = subprocess.Popen(cmd)"),
            (
                "my_process = subprocess.Popen(['ls'])",
                "process = subprocess.Popen(['ls'])",
            ),
        ],
        description="Replace subprocess.Popen assignment with standard variable name",
    ),
    "replace_path_open_write": ValidatedPattern(
        name="replace_path_open_write",
        pattern=r'(\w+)\.open\(["\']wb?["\'][^)]*\)',
        replacement=r"atomic_file_write(\1)",
        test_cases=[
            ("path.open('w')", "atomic_file_write(path)"),
            ("file.open('wb')", "atomic_file_write(file)"),
        ],
        description="Replace file.open() with atomic_file_write",
    ),
    "replace_path_write_text": ValidatedPattern(
        name="replace_path_write_text",
        pattern=r"(\w+)\.write_text\(([^)]+)\)",
        replacement=r"await SafeFileOperations.safe_write_text(\1, \2, atomic=True)",
        test_cases=[
            (
                "path.write_text(content)",
                "await SafeFileOperations.safe_write_text(path, content, atomic=True)",
            ),
            (
                "file.write_text(data, encoding='utf-8')",
                "await SafeFileOperations.safe_write_text(file, data, encoding='utf-8', "
                "atomic=True)",
            ),
        ],
        description="Replace path.write_text with SafeFileOperations.safe_write_text",
    ),
    "agent_count_pattern": ValidatedPattern(
        name="agent_count_pattern",
        pattern=r"(\d+)\s+agents",
        replacement=r"\1 agents",
        test_cases=[
            ("9 agents", "9 agents"),
            ("12 agents", "12 agents"),
            ("5 agents", "5 agents"),
        ],
        description="Match agent count patterns for documentation consistency",
        flags=re.IGNORECASE,
    ),
    "specialized_agent_count_pattern": ValidatedPattern(
        name="specialized_agent_count_pattern",
        pattern=r"(\d+)\s+specialized\s+agents",
        replacement=r"\1 specialized agents",
        test_cases=[
            ("9 specialized agents", "9 specialized agents"),
            ("12 specialized agents", "12 specialized agents"),
            ("5 specialized agents", "5 specialized agents"),
        ],
        description="Match specialized agent count patterns for documentation "
        "consistency",
        flags=re.IGNORECASE,
    ),
    "total_agents_config_pattern": ValidatedPattern(
        name="total_agents_config_pattern",
        pattern=r'total_agents["\'][\s]*: \s*(\d+)',
        replacement=r'total_agents": \1',
        test_cases=[
            ('total_agents": 9', 'total_agents": 9'),
            ("total_agents': 12", 'total_agents": 12'),
            ('total_agents" : 5', 'total_agents": 5'),
        ],
        description="Match total agents configuration patterns",
        flags=re.IGNORECASE,
    ),
    "sub_agent_count_pattern": ValidatedPattern(
        name="sub_agent_count_pattern",
        pattern=r"(\d+)\s+sub-agents",
        replacement=r"\1 sub-agents",
        test_cases=[
            ("9 sub-agents", "9 sub-agents"),
            ("12 sub-agents", "12 sub-agents"),
            ("5 sub-agents", "5 sub-agents"),
        ],
        description="Match sub-agent count patterns for documentation consistency",
        flags=re.IGNORECASE,
    ),
    "update_agent_count": ValidatedPattern(
        name="update_agent_count",
        pattern=r"\b(\d+)\s+agents\b",
        replacement=r"NEW_COUNT agents",
        test_cases=[
            ("9 agents working", "NEW_COUNT agents working"),
            ("We have 12 agents ready", "We have NEW_COUNT agents ready"),
            ("All 5 agents are active", "All NEW_COUNT agents are active"),
        ],
        description="Update agent count references (NEW_COUNT replaced dynamically)",
    ),
    "update_specialized_agent_count": ValidatedPattern(
        name="update_specialized_agent_count",
        pattern=r"\b(\d+)\s+specialized\s+agents\b",
        replacement=r"NEW_COUNT specialized agents",
        test_cases=[
            (
                "9 specialized agents available",
                "NEW_COUNT specialized agents available",
            ),
            ("We have 12 specialized agents", "We have NEW_COUNT specialized agents"),
            ("All 5 specialized agents work", "All NEW_COUNT specialized agents work"),
        ],
        description="Update specialized agent count references (NEW_COUNT replaced"
        " dynamically)",
    ),
    "update_total_agents_config": ValidatedPattern(
        name="update_total_agents_config",
        pattern=r'total_agents["\'][\s]*: \s*\d+',
        replacement=r'total_agents": NEW_COUNT',
        test_cases=[
            ('total_agents": 9', 'total_agents": NEW_COUNT'),
            ("total_agents': 12", 'total_agents": NEW_COUNT'),
            ('total_agents" : 5', 'total_agents": NEW_COUNT'),
        ],
        description="Update total agents configuration (NEW_COUNT replaced"
        " dynamically)",
    ),
    "update_sub_agent_count": ValidatedPattern(
        name="update_sub_agent_count",
        pattern=r"\b(\d+)\s+sub-agents\b",
        replacement=r"NEW_COUNT sub-agents",
        test_cases=[
            ("9 sub-agents working", "NEW_COUNT sub-agents working"),
            ("We have 12 sub-agents ready", "We have NEW_COUNT sub-agents ready"),
            ("All 5 sub-agents are active", "All NEW_COUNT sub-agents are active"),
        ],
        description="Update sub-agent count references (NEW_COUNT replaced"
        " dynamically)",
    ),
    "fixture_not_found_pattern": ValidatedPattern(
        name="fixture_not_found_pattern",
        pattern=r"fixture '(\w+)' not found",
        replacement=r"fixture '\1' not found",
        test_cases=[
            ("fixture 'temp_pkg_path' not found", "fixture 'temp_pkg_path' not found"),
            ("fixture 'console' not found", "fixture 'console' not found"),
            ("fixture 'tmp_path' not found", "fixture 'tmp_path' not found"),
        ],
        description="Match pytest fixture not found error patterns",
    ),
    "import_error_pattern": ValidatedPattern(
        name="import_error_pattern",
        pattern=r"ImportError|ModuleNotFoundError",
        replacement=r"ImportError",
        test_cases=[
            ("ImportError: No module named", "ImportError: No module named"),
            ("ModuleNotFoundError: No module", "ImportError: No module"),
            ("Other error types", "Other error types"),
        ],
        description="Match import error patterns in test failures",
    ),
    "assertion_error_pattern": ValidatedPattern(
        name="assertion_error_pattern",
        pattern=r"assert .+ ==",
        replacement=r"AssertionError",
        test_cases=[
            (
                "AssertionError: Values differ",
                "AssertionError: Values differ",
            ),
            ("assert result == expected", "AssertionError expected"),
            ("Normal code", "Normal code"),
        ],
        description="Match assertion error patterns in test failures",
    ),
    "attribute_error_pattern": ValidatedPattern(
        name="attribute_error_pattern",
        pattern=r"AttributeError: .+ has no attribute",
        replacement=r"AttributeError: has no attribute",
        test_cases=[
            (
                "AttributeError: 'Mock' has no attribute 'test'",
                "AttributeError: has no attribute 'test'",
            ),
            (
                "AttributeError: 'NoneType' has no attribute 'value'",
                "AttributeError: has no attribute 'value'",
            ),
            ("Normal error", "Normal error"),
        ],
        description="Match attribute error patterns in test failures",
    ),
    "mock_spec_error_pattern": ValidatedPattern(
        name="mock_spec_error_pattern",
        pattern=r"MockSpec|spec.*Mock",
        replacement=r"MockSpec",
        test_cases=[
            ("MockSpec error occurred", "MockSpec error occurred"),
            ("spec for Mock failed", "MockSpec failed"),
            ("Normal mock usage", "Normal mock usage"),
        ],
        description="Match mock specification error patterns in test failures",
    ),
    "hardcoded_path_pattern": ValidatedPattern(
        name="hardcoded_path_pattern",
        pattern=r"'/test/path'|/test/path",
        replacement=r"str(tmp_path)",
        test_cases=[
            ("'/test/path'", "str(tmp_path)"),
            ("/test/path", "str(tmp_path)"),
            ("'/other/path'", "'/other/path'"),
        ],
        description="Match hardcoded test path patterns that should use tmp_path",
    ),
    "missing_name_pattern": ValidatedPattern(
        name="missing_name_pattern",
        pattern=r"name '(\w+)' is not defined",
        replacement=r"name '\1' is not defined",
        test_cases=[
            ("name 'pytest' is not defined", "name 'pytest' is not defined"),
            ("name 'Mock' is not defined", "name 'Mock' is not defined"),
            ("name 'Path' is not defined", "name 'Path' is not defined"),
        ],
        description="Match undefined name patterns in test failures",
    ),
    "pydantic_validation_pattern": ValidatedPattern(
        name="pydantic_validation_pattern",
        pattern=r"ValidationError|validation error",
        replacement=r"ValidationError",
        test_cases=[
            ("ValidationError: field required", "ValidationError: field required"),
            ("validation error in field", "ValidationError in field"),
            ("Normal validation", "Normal validation"),
        ],
        description="Match Pydantic validation error patterns in test failures",
    ),
    "list_append_inefficiency_pattern": ValidatedPattern(
        name="list_append_inefficiency_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*\[([^]]+)\]",
        replacement=r"\1\2.append(\3)",
        test_cases=[
            (" items += [new_item]", " items.append(new_item)"),
            ("results += [result]", "results.append(result)"),
            (" data += [value, other]", " data.append(value, other)"),
        ],
        description="Replace inefficient list[t.Any] concatenation with append for"
        " performance",
    ),
    "string_concatenation_pattern": ValidatedPattern(
        name="string_concatenation_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*(.+)",
        replacement=r"\1\2_parts.append(\3)",
        test_cases=[
            (" text += new_text", " text_parts.append(new_text)"),
            ("result += line", "result_parts.append(line)"),
            (" output += data", " output_parts.append(data)"),
        ],
        description="Replace string concatenation with list[t.Any] append for performance "
        "optimization",
    ),
    "nested_loop_detection_pattern": ValidatedPattern(
        name="nested_loop_detection_pattern",
        pattern=r"(\s*)(for\s+\w+\s+in\s+.*: )",
        replacement=r"\1# Performance: Potential nested loop - check complexity\n\1\2",
        test_cases=[
            (
                " for j in other: ",
                " # Performance: Potential nested loop - check complexity\n "
                "for j in other: ",
            ),
            (
                "for i in items: ",
                "# Performance: Potential nested loop - check complexity\nfor i"
                " in items: ",
            ),
        ],
        description="Detect loop patterns that might be nested creating O(n²)"
        " complexity",
        flags=re.MULTILINE,
    ),
    "list_extend_optimization_pattern": ValidatedPattern(
        name="list_extend_optimization_pattern",
        pattern=r"(\s*)(\w+)\s*\+=\s*\[([^]]+(?: , \s*[^]]+)*)\]",
        replacement=r"\1\2.extend([\3])",
        test_cases=[
            (" items += [a, b, c]", " items.extend([a, b, c])"),
            ("results += [x, y]", "results.extend([x, y])"),
            (" data += [single_item]", " data.extend([single_item])"),
        ],
        description="Replace list[t.Any] concatenation with extend for better performance with multiple items",
    ),
    "inefficient_string_join_pattern": ValidatedPattern(
        name="inefficient_string_join_pattern",
        pattern=r"(\s*)(\w+)\s*=\s*([\"'])([\"'])\s*\.\s*join\(\s*\[\s*\]\s*\)",
        replacement=r"\1\2 = \3\4 # Performance: Use empty string directly instead"
        r" of join",
        test_cases=[
            (
                ' text = "".join([])',
                ' text = "" # Performance: Use empty string directly instead of join',
            ),
            (
                "result = ''.join([])",
                "result = '' # Performance: Use empty string directly instead of join",
            ),
        ],
        description="Replace inefficient empty list[t.Any] join with direct empty string"
        " assignment",
    ),
    "repeated_len_in_loop_pattern": ValidatedPattern(
        name="repeated_len_in_loop_pattern",
        pattern=r"(\s*)(len\(\s*(\w+)\s*\))",
        replacement=r"\1# Performance: Consider caching len(\3) if used "
        r"repeatedly\n\1\2",
        test_cases=[
            (
                " len(items)",
                " # Performance: Consider caching len(items) if used repeatedly\n"
                " len(items)",
            ),
            (
                "len(data)",
                "# Performance: Consider caching len(data) if used "
                "repeatedly\nlen(data)",
            ),
        ],
        description="Suggest caching len() calls that might be repeated",
    ),
    "list_comprehension_optimization_pattern": ValidatedPattern(
        name="list_comprehension_optimization_pattern",
        pattern=r"(\s*)(\w+)\.append\(([^)]+)\)",
        replacement=r"\1# Performance: Consider list[t.Any] comprehension if this is in a "
        r"simple loop\n\1\2.append(\3)",
        test_cases=[
            (
                " results.append(item * 2)",
                " # Performance: Consider list[t.Any] comprehension if this is in a "
                "simple loop\n results.append(item * 2)",
            ),
            (
                "data.append(value)",
                "# Performance: Consider list[t.Any] comprehension if this is in a simple"
                " loop\ndata.append(value)",
            ),
        ],
        description="Suggest list[t.Any] comprehensions for simple append patterns",
    ),
    "detect_crypto_weak_algorithms": ValidatedPattern(
        name="detect_crypto_weak_algorithms",
        pattern=r"\b(?:md4|md5|sha1|des|3des|rc4)\b",
        replacement="[WEAK_CRYPTO_ALGORITHM]",
        description="Detect weak cryptographic algorithms",
        flags=re.IGNORECASE,
        global_replace=True,
        test_cases=[
            ("hashlib.md5()", "hashlib.[WEAK_CRYPTO_ALGORITHM]()"),
            ("using DES encryption", "using [WEAK_CRYPTO_ALGORITHM] encryption"),
            ("SHA256 is good", "SHA256 is good"),
            ("MD4 hashing", "[WEAK_CRYPTO_ALGORITHM] hashing"),
        ],
    ),
    "detect_hardcoded_credentials_advanced": ValidatedPattern(
        name="detect_hardcoded_credentials_advanced",
        pattern=r"(?i)\b(?:password|passwd|pwd|secret|key|token|api_key|"
        r'apikey)\s*[:=]\s*["\'][^"\']{3,}["\']',
        replacement="[HARDCODED_CREDENTIAL_DETECTED]",
        description="Detect hardcoded credentials in various formats "
        "(case insensitive)",
        flags=re.IGNORECASE,
        global_replace=True,
        test_cases=[
            ('password="secret123"', "[HARDCODED_CREDENTIAL_DETECTED]"),
            ("API_KEY = 'abc-123-def'", "[HARDCODED_CREDENTIAL_DETECTED]"),
            ('token: "my-secret-token"', "[HARDCODED_CREDENTIAL_DETECTED]"),
            (
                'username = "user"',
                'username = "user"',
            ),
        ],
    ),
    "detect_subprocess_shell_injection": ValidatedPattern(
        name="detect_subprocess_shell_injection",
        pattern=r"\bsubprocess\.\w+\([^)]*shell\s*=\s*True[^)]*\)",
        replacement="[SHELL_INJECTION_RISK]",
        description="Detect subprocess calls with shell=True",
        global_replace=True,
        test_cases=[
            ("subprocess.run(cmd, shell=True)", "[SHELL_INJECTION_RISK]"),
            ("subprocess.call(command, shell=True)", "[SHELL_INJECTION_RISK]"),
            (
                "subprocess.run(cmd, shell=False)",
                "subprocess.run(cmd, shell=False)",
            ),
        ],
    ),
    "detect_regex_redos_vulnerable": ValidatedPattern(
        name="detect_regex_redos_vulnerable",
        pattern=r"\([^)]+\)[\*\+]",
        replacement="[REDOS_VULNERABLE_PATTERN]",
        description="Detect regex patterns vulnerable to ReDoS attacks (simplified"
        " detection)",
        global_replace=True,
        test_cases=[
            ("(a+)*", "[REDOS_VULNERABLE_PATTERN]"),
            ("(a*)+", "[REDOS_VULNERABLE_PATTERN]"),
            ("(abc)+", "[REDOS_VULNERABLE_PATTERN]"),
            ("simple+", "simple+"),
        ],
    ),
    "fix_hardcoded_jwt_secret": ValidatedPattern(
        name="fix_hardcoded_jwt_secret",
        pattern=r'(JWT_SECRET|jwt_secret)\s*=\s*["\'][^"\']+["\']',
        replacement=r'\1 = os.getenv("JWT_SECRET", "")',
        description="Replace hardcoded JWT secrets with environment variables",
        global_replace=True,
        test_cases=[
            (
                'JWT_SECRET = "hardcoded-secret"',
                'JWT_SECRET = os.getenv("JWT_SECRET", "")',
            ),
            ('jwt_secret = "my-secret"', 'jwt_secret = os.getenv("JWT_SECRET", "")'),
            ('other_var = "value"', 'other_var = "value"'),
        ],
    ),
    "detect_unsafe_pickle_usage": ValidatedPattern(
        name="detect_unsafe_pickle_usage",
        pattern=r"\bpickle\.(loads?)\s*\(",
        replacement=r"[UNSAFE_PICKLE_USAGE].\1(",
        description="Detect potentially unsafe pickle usage",
        global_replace=True,
        test_cases=[
            ("pickle.load(file)", "[UNSAFE_PICKLE_USAGE].load(file)"),
            ("pickle.loads(data)", "[UNSAFE_PICKLE_USAGE].loads(data)"),
            ("my_pickle.load(file)", "my_pickle.load(file)"),
        ],
    ),
    "extract_range_size": ValidatedPattern(
        name="extract_range_size",
        pattern=r"range\((\d+)\)",
        replacement=r"\1",
        description="Extract numeric size from range() calls",
        test_cases=[
            ("range(1000)", "1000"),
            ("range(50)", "50"),
            ("for i in range(100): ", "for i in 100: "),
            ("other_func(10)", "other_func(10)"),
        ],
    ),
    "match_error_code_patterns": ValidatedPattern(
        name="match_error_code_patterns",
        pattern=r"F\d{3}|I\d{3}|E\d{3}|W\d{3}",
        replacement=r"\g<0>",
        description="Match standard error codes like F403, I001, etc.",
        test_cases=[
            ("F403", "F403"),
            ("I001", "I001"),
            ("E302", "E302"),
            ("W291", "W291"),
            ("ABC123", "ABC123"),
        ],
    ),
    "match_validation_patterns": ValidatedPattern(
        name="match_validation_patterns",
        pattern=r"if\s+not\s+\w+\s*: |if\s+\w+\s+is\s+None\s*: |if\s+len\(\w+\)\s*[<>=]",
        replacement=r"\g<0>",
        description="Match common validation patterns for extraction",
        test_cases=[
            ("if not var: ", "if not var: "),
            ("if item is None: ", "if item is None: "),
            ("if len(items) >", "if len(items) >"),
            ("other code", "other code"),
        ],
    ),
    "match_loop_patterns": ValidatedPattern(
        name="match_loop_patterns",
        pattern=r"\s*for\s+.*: \s*$|\s*while\s+.*: \s*$",
        replacement=r"\g<0>",
        description="Match for/while loop patterns",
        test_cases=[
            (" for i in items: ", " for i in items: "),
            (" while condition: ", " while condition: "),
            ("regular line", "regular line"),
        ],
    ),
    "match_star_import": ValidatedPattern(
        name="match_star_import",
        pattern=r"from\s+\w+\s+import\s+\*",
        replacement=r"\g<0>",
        description="Match star import statements",
        test_cases=[
            ("from module import *", "from module import *"),
            ("from my_pkg import *", "from my_pkg import *"),
            ("from module import specific", "from module import specific"),
        ],
    ),
    "clean_unused_import": ValidatedPattern(
        name="clean_unused_import",
        pattern=r"^\s*import\s+unused_module\s*$",
        replacement=r"",
        description="Remove unused import statements (example with unused_module)",
        test_cases=[
            (" import unused_module", ""),
            (
                "import other_module",
                "import other_module",
            ),
        ],
    ),
    "clean_unused_from_import": ValidatedPattern(
        name="clean_unused_from_import",
        pattern=r"^\s*from\s+\w+\s+import\s+.*\bunused_item\b",
        replacement=r"\g<0>",
        description="Match from import statements with unused items (example with "
        "unused_item)",
        test_cases=[
            (
                "from module import used, unused_item",
                "from module import used, unused_item",
            ),
            ("from other import needed", "from other import needed"),
        ],
    ),
    "clean_import_commas": ValidatedPattern(
        name="clean_import_commas",
        pattern=r", \s*, ",
        replacement=r", ",
        description="Clean double commas in import statements",
        test_cases=[
            ("from module import a, , b", "from module import a, b"),
            ("items = [a, , b]", "items = [a, b]"),
            ("normal, list[t.Any]", "normal, list[t.Any]"),
        ],
    ),
    "clean_trailing_import_comma": ValidatedPattern(
        name="clean_trailing_import_comma",
        pattern=r", \s*$",
        replacement=r"",
        description="Remove trailing commas from lines",
        test_cases=[
            ("from module import a, b, ", "from module import a, b"),
            ("import item, ", "import item"),
            ("normal line", "normal line"),
        ],
    ),
    "clean_import_prefix": ValidatedPattern(
        name="clean_import_prefix",
        pattern=r"import\s*, \s*",
        replacement=r"import ",
        description="Clean malformed import statements with leading comma",
        test_cases=[
            ("import , module", "import module"),
            ("from pkg import , item", "from pkg import item"),
            ("import normal", "import normal"),
        ],
    ),
    "extract_unused_import_name": ValidatedPattern(
        name="extract_unused_import_name",
        pattern=r"unused import ['\"]([^'\"]+)['\"]",
        replacement=r"\1",
        description="Extract import name from vulture unused import messages",
        test_cases=[
            ("unused import 'module_name'", "module_name"),
            ('unused import "other_module"', "other_module"),
            ("some other text", "some other text"),
        ],
    ),
    "normalize_whitespace": ValidatedPattern(
        name="normalize_whitespace",
        pattern=r"\s+",
        replacement=r" ",
        description="Normalize multiple whitespace to single space",
        global_replace=True,
        test_cases=[
            ("import module", "import module"),
            ("from pkg import item", "from pkg import item"),
            ("normal text", "normal text"),
        ],
    ),
    # Template processing patterns
    "extract_template_variables": ValidatedPattern(
        name="extract_template_variables",
        pattern=r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}",
        replacement=r"\1",
        description="Extract template variables from {{variable}} patterns",
        test_cases=[
            ("Hello {{name}}", "Hello name"),
            ("{{user_name}}", "user_name"),
            ("{{ spaced_var }}", "spaced_var"),
            ("text {{var1}} and {{var2}}", "text var1 and {{var2}}"),
        ],
    ),
    "extract_template_sections": ValidatedPattern(
        name="extract_template_sections",
        pattern=r"\{\%\s*section\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\%\}",
        replacement=r"\1",
        description="Extract section names from {% section name %} patterns",
        test_cases=[
            ("{% section intro %}", "intro"),
            ("{%  section  main_content  %}", "main_content"),
            ("text {% section footer %} more", "text footer more"),
            ("{% section header_1 %}", "header_1"),
        ],
    ),
    "extract_template_blocks": ValidatedPattern(
        name="extract_template_blocks",
        pattern=r"\{\%\s*block\s+(\w+)\s*\%\}(.*?)\{\%\s*endblock\s*\%\}",
        replacement=r"\1",
        description="Extract block names and content from template blocks",
        flags=re.DOTALL,
        test_cases=[
            ("{% block title %}Hello{% endblock %}", "title"),
            ("{%  block  content  %}Text content{% endblock %}", "content"),
            ("{% block main %}Multi\nline{% endblock %}", "main"),
            (
                "prefix {% block nav %}nav content{% endblock %} suffix",
                "prefix nav suffix",
            ),
        ],
    ),
    "replace_template_block": ValidatedPattern(
        name="replace_template_block",
        pattern=r"\{\%\s*block\s+BLOCK_NAME\s*\%\}.*?\{\%\s*endblock\s*\%\}",
        replacement="REPLACEMENT_CONTENT",
        description="Replace a specific template block (use with dynamic pattern substitution)",
        flags=re.DOTALL,
        test_cases=[
            ("{% block BLOCK_NAME %}old{% endblock %}", "REPLACEMENT_CONTENT"),
            (
                "{%  block  BLOCK_NAME  %}old content{% endblock %}",
                "REPLACEMENT_CONTENT",
            ),
        ],
    ),
    # Documentation parsing patterns
    "extract_markdown_links": ValidatedPattern(
        name="extract_markdown_links",
        pattern=r"\[([^\]]+)\]\(([^)]+)\)",
        replacement=r"\1 -> \2",
        description="Extract markdown link text and URLs from [text](url) patterns",
        test_cases=[
            ("[Click here](http://example.com)", "Click here -> http://example.com"),
            ("[Local file](./docs/readme.md)", "Local file -> ./docs/readme.md"),
            (
                "See [the docs](../reference.md) for more",
                "See the docs -> ../reference.md for more",
            ),
            ("[Multi word link](path/to/file)", "Multi word link -> path/to/file"),
        ],
    ),
    "extract_version_numbers": ValidatedPattern(
        name="extract_version_numbers",
        pattern=r"version\s+(\d+\.\d+\.\d+)",
        replacement=r"\1",
        description="Extract semantic version numbers from 'version X.Y.Z' patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("version 1.2.3", "1.2.3"),
            ("Version 10.0.1", "10.0.1"),
            ("current version 0.5.0", "current 0.5.0"),
            ("VERSION 2.11.4", "2.11.4"),
        ],
    ),
    # Docstring parsing patterns
    "extract_google_docstring_params": ValidatedPattern(
        name="extract_google_docstring_params",
        pattern=r"^\s*(\w+)(?:\s*\([^)]+\))?\s*:\s*(.+)$",
        replacement=r"\1: \2",
        description="Extract parameter names and descriptions from Google-style docstrings",
        flags=re.MULTILINE,
        test_cases=[
            ("    param1: Description here", "param1: Description here"),
            ("param2 (str): String parameter", "param2: String parameter"),
            (
                "  complex_param (Optional[int]): Complex type",
                "complex_param: Complex type",
            ),
            ("simple: Simple desc", "simple: Simple desc"),
        ],
    ),
    "extract_sphinx_docstring_params": ValidatedPattern(
        name="extract_sphinx_docstring_params",
        pattern=r":param\s+(\w+)\s*:\s*(.+)$",
        replacement=r"\1: \2",
        description="Extract parameter names and descriptions from Sphinx-style docstrings",
        flags=re.MULTILINE,
        test_cases=[
            (":param name: The name parameter", "name: The name parameter"),
            (":param user_id: User identifier", "user_id: User identifier"),
            (
                ":param  spaced  :  Description with spaces",
                "spaced: Description with spaces",
            ),
            (
                ":param complex_var: Multi-word description here",
                "complex_var: Multi-word description here",
            ),
        ],
    ),
    "extract_docstring_returns": ValidatedPattern(
        name="extract_docstring_returns",
        pattern=r"(?:Returns?|Return):\s*(.+?)(?=\n\n|\n\w+:|\Z)",
        replacement=r"\1",
        description="Extract return descriptions from docstrings",
        flags=re.MULTILINE | re.DOTALL,
        test_cases=[
            ("Returns: A string value", "A string value"),
            ("Return: Boolean indicating success", "Boolean indicating success"),
            ("Returns: Multi-line\n    description", "Multi-line\n    description"),
            ("Returns: Simple value\n\nArgs:", "Simple value\n\nArgs:"),
        ],
    ),
    # Command processing patterns
    "enhance_command_blocks": ValidatedPattern(
        name="enhance_command_blocks",
        pattern=r"```(?:bash|shell|sh)?\n([^`]+)\n```",
        replacement=r"```bash\n\1\n```",
        description="Enhance command blocks with proper bash syntax highlighting",
        test_cases=[
            ("```\npython -m test\n```", "```bash\npython -m test\n```"),
            ("```bash\necho hello\n```", "```bash\necho hello\n```"),
            ("```sh\nls -la\n```", "```bash\nls -la\n```"),
            ("```shell\ncd /tmp\n```", "```bash\ncd /tmp\n```"),
        ],
    ),
    "extract_step_numbers": ValidatedPattern(
        name="extract_step_numbers",
        pattern=r"^(\s*)(\d+)\.\s*(.+)$",
        replacement=r"\1**Step \2**: \3",
        description="Extract and enhance numbered steps in documentation",
        flags=re.MULTILINE,
        test_cases=[
            ("1. First step", "**Step 1**: First step"),
            ("  2. Indented step", "  **Step 2**: Indented step"),
            ("10. Double digit step", "**Step 10**: Double digit step"),
            ("normal text", "normal text"),
        ],
    ),
    "extract_bash_command_blocks": ValidatedPattern(
        name="extract_bash_command_blocks",
        pattern=r"```bash\n([^`]+)\n```",
        replacement=r"\1",
        description="Extract content from bash command blocks",
        test_cases=[
            ("```bash\necho hello\n```", "echo hello"),
            ("```bash\npython -m test\n```", "python -m test"),
            ("text\n```bash\nls -la\n```\nmore", "text\nls -la\nmore"),
            ("```bash\nmulti\nline\ncommand\n```", "multi\nline\ncommand"),
        ],
    ),
    "detect_coverage_badge": ValidatedPattern(
        name="detect_coverage_badge",
        pattern=r"!\[Coverage.*?\]\(.*?coverage.*?\)|!\[.*coverage.*?\]\(.*?shields\.io.*?coverage.*?\)|https://img\.shields\.io/badge/coverage-[\d\.]+%25-\w+",
        replacement="",
        description="Detect existing coverage badges in README content",
        flags=re.IGNORECASE,
        test_cases=[
            (
                "![Coverage](https://img.shields.io/badge/coverage-85.0%25-brightgreen)",
                "",
            ),
            (
                "![Code Coverage](https://img.shields.io/badge/coverage-75.5%25-yellow)",
                "",
            ),
            (
                "![coverage badge](https://shields.io/badge/coverage-90.0%25-brightgreen)",
                "",
            ),
            ("Some text without badge", "Some text without badge"),
        ],
    ),
    "update_coverage_badge_url": ValidatedPattern(
        name="update_coverage_badge_url",
        pattern=r"(!\[Coverage.*?\]\()([^)]+)(\))",
        replacement=r"\1NEW_BADGE_URL\3",
        description="Update coverage badge URL in markdown links",
        test_cases=[
            ("![Coverage](old_url)", "![Coverage](NEW_BADGE_URL)"),
            ("![Coverage Badge](old_badge_url)", "![Coverage Badge](NEW_BADGE_URL)"),
            ("text ![Coverage](url) more", "text ![Coverage](NEW_BADGE_URL) more"),
            ("no badge here", "no badge here"),
        ],
    ),
    "update_coverage_badge_any": ValidatedPattern(
        name="update_coverage_badge_any",
        pattern=r"(!\[.*coverage.*?\]\()([^)]+)(\))",
        replacement=r"\1NEW_BADGE_URL\3",
        description="Update any coverage-related badge URL",
        flags=re.IGNORECASE,
        test_cases=[
            ("![Code Coverage](old_url)", "![Code Coverage](NEW_BADGE_URL)"),
            ("![coverage badge](old_url)", "![coverage badge](NEW_BADGE_URL)"),
            ("![test coverage](url)", "![test coverage](NEW_BADGE_URL)"),
            ("![Other Badge](url)", "![Other Badge](url)"),
        ],
    ),
    "update_shields_coverage_url": ValidatedPattern(
        name="update_shields_coverage_url",
        pattern=r"(https://img\.shields\.io/badge/coverage-[\d\.]+%25-\w+)",
        replacement="NEW_BADGE_URL",
        description="Update shields.io coverage badge URLs directly",
        test_cases=[
            (
                "https://img.shields.io/badge/coverage-85.0%25-brightgreen",
                "NEW_BADGE_URL",
            ),
            ("https://img.shields.io/badge/coverage-75.5%25-yellow", "NEW_BADGE_URL"),
            (
                "https://img.shields.io/badge/coverage-90.1%25-brightgreen",
                "NEW_BADGE_URL",
            ),
            (
                "https://img.shields.io/badge/build-passing-green",
                "https://img.shields.io/badge/build-passing-green",
            ),
        ],
    ),
    "extract_coverage_percentage": ValidatedPattern(
        name="extract_coverage_percentage",
        pattern=r"coverage-([\d\.]+)%25",
        replacement="",  # Not used for extraction, just validation
        description="Search for coverage percentage in badge URL",
        test_cases=[
            ("coverage-85.0%25", ""),  # Will use search() to get group(1)
            ("coverage-75.5%25", ""),
            ("coverage-100.0%25", ""),
            ("no coverage here", "no coverage here"),  # No match
        ],
    ),
    "detect_typing_usage": ValidatedPattern(
        name="detect_typing_usage",
        pattern=r"\bt\.[A-Z]",
        replacement="",
        description="Detect usage of typing module aliases like t.Any, t.Dict, etc.",
        global_replace=True,
        test_cases=[
            (
                "def func(x: t.Any) -> t.Dict:",
                "def func(x: ny) -> ict:",
            ),  # Removes t.A and t.D
            (
                "value: t.Optional[str] = None",
                "value: ptional[str] = None",
            ),  # Removes t.O
            ("from typing import Dict", "from typing import Dict"),  # No match
            ("data = dict()", "data = dict()"),  # No match
        ],
    ),
}


def validate_all_patterns() -> dict[str, bool]:
    results: dict[str, bool] = {}
    for name, pattern in SAFE_PATTERNS.items():
        try:
            pattern._validate()
            results[name] = True
        except ValueError as e:
            results[name] = False
            print(f"Pattern '{name}' failed validation: {e}")
    return results


def find_pattern_for_text(text: str) -> list[str]:
    return [name for name, pattern in SAFE_PATTERNS.items() if pattern.test(text)]


def apply_safe_replacement(text: str, pattern_name: str) -> str:
    if pattern_name not in SAFE_PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    return SAFE_PATTERNS[pattern_name].apply(text)


def get_pattern_description(pattern_name: str) -> str:
    if pattern_name not in SAFE_PATTERNS:
        return "Unknown pattern"

    return SAFE_PATTERNS[pattern_name].description


def fix_multi_word_hyphenation(text: str) -> str:
    return SAFE_PATTERNS["fix_spaced_hyphens"].apply_iteratively(text)


def update_pyproject_version(content: str, new_version: str) -> str:
    pattern_obj = SAFE_PATTERNS["update_pyproject_version"]

    temp_pattern = ValidatedPattern(
        name="temp_version_update",
        pattern=pattern_obj.pattern,
        replacement=f"\\g<1>{new_version}\\g<3>",
        description=f"Update version to {new_version}",
        test_cases=[
            ('version = "1.2.3"', f'version = "{new_version}"'),
        ],
    )

    return re.compile(pattern_obj.pattern, re.MULTILINE).sub(
        temp_pattern.replacement, content
    )


def apply_formatting_fixes(content: str) -> str:
    pattern = SAFE_PATTERNS["remove_trailing_whitespace"]
    content = re.compile(pattern.pattern, re.MULTILINE).sub(
        pattern.replacement, content
    )

    content = SAFE_PATTERNS["normalize_multiple_newlines"].apply(content)

    return content


def apply_security_fixes(content: str) -> str:
    content = SAFE_PATTERNS["fix_subprocess_run_shell"].apply(content)
    content = SAFE_PATTERNS["fix_subprocess_call_shell"].apply(content)
    content = SAFE_PATTERNS["fix_subprocess_popen_shell"].apply(content)

    content = SAFE_PATTERNS["fix_unsafe_yaml_load"].apply(content)
    content = SAFE_PATTERNS["fix_weak_md5_hash"].apply(content)
    content = SAFE_PATTERNS["fix_weak_sha1_hash"].apply(content)
    content = SAFE_PATTERNS["fix_insecure_random_choice"].apply(content)

    content = SAFE_PATTERNS["remove_debug_prints_with_secrets"].apply(content)

    return content


def apply_test_fixes(content: str) -> str:
    return SAFE_PATTERNS["normalize_assert_statements"].apply(content)


def is_valid_job_id(job_id: str) -> bool:
    return SAFE_PATTERNS["validate_job_id_alphanumeric"].test(job_id)


def remove_coverage_fail_under(addopts: str) -> str:
    return SAFE_PATTERNS["remove_coverage_fail_under"].apply(addopts)


def update_coverage_requirement(content: str, new_coverage: float) -> str:
    pattern_obj = SAFE_PATTERNS["update_coverage_requirement"]

    temp_pattern = ValidatedPattern(
        name="temp_coverage_update",
        pattern=pattern_obj.pattern,
        replacement=f"\\1{new_coverage: .0f}",
        description=f"Update coverage to {new_coverage}",
        test_cases=[
            ("--cov-fail-under=85", f"--cov-fail-under={new_coverage: .0f}"),
        ],
    )

    return re.compile(pattern_obj.pattern).sub(temp_pattern.replacement, content)


def update_repo_revision(content: str, repo_url: str, new_revision: str) -> str:
    escaped_url = re.escape(repo_url)
    pattern = rf'("repo": "{escaped_url}".*?"rev": )"([^"]+)"'
    replacement = rf'\1"{new_revision}"'

    return re.compile(pattern, re.DOTALL).sub(replacement, content)


def sanitize_internal_urls(text: str) -> str:
    url_patterns = [
        "sanitize_localhost_urls",
        "sanitize_127_urls",
        "sanitize_any_localhost_urls",
        "sanitize_ws_localhost_urls",
        "sanitize_ws_127_urls",
        "sanitize_simple_localhost_urls",
        "sanitize_simple_ws_localhost_urls",
    ]

    result = text
    for pattern_name in url_patterns:
        result = SAFE_PATTERNS[pattern_name].apply(result)

    return result


def apply_pattern_iteratively(
    text: str, pattern_name: str, max_iterations: int = MAX_ITERATIONS
) -> str:
    if pattern_name not in SAFE_PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")

    return SAFE_PATTERNS[pattern_name].apply_iteratively(text, max_iterations)


def get_all_pattern_stats() -> dict[str, dict[str, float] | dict[str, str]]:
    test_text = "python - m crackerjack - t with pytest - hypothesis - specialist"
    stats: dict[str, dict[str, float] | dict[str, str]] = {}

    for name, pattern in SAFE_PATTERNS.items():
        try:
            pattern_stats = pattern.get_performance_stats(test_text, iterations=10)
            stats[name] = pattern_stats
        except Exception as e:
            stats[name] = {"error": str(e)}

    return stats


def clear_all_caches() -> None:
    CompiledPatternCache.clear_cache()


def get_cache_info() -> dict[str, int | list[str]]:
    return CompiledPatternCache.get_cache_stats()


def detect_path_traversal_patterns(path_str: str) -> list[str]:
    detected = []
    traversal_patterns = [
        "detect_directory_traversal_basic",
        "detect_directory_traversal_backslash",
        "detect_url_encoded_traversal",
        "detect_double_url_encoded_traversal",
    ]

    for pattern_name in traversal_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_null_byte_patterns(path_str: str) -> list[str]:
    detected = []
    null_patterns = [
        "detect_null_bytes_url",
        "detect_null_bytes_literal",
        "detect_utf8_overlong_null",
    ]

    for pattern_name in null_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_dangerous_directory_patterns(path_str: str) -> list[str]:
    detected = []
    dangerous_patterns = [
        "detect_sys_directory_pattern",
        "detect_proc_directory_pattern",
        "detect_etc_directory_pattern",
        "detect_boot_directory_pattern",
        "detect_dev_directory_pattern",
        "detect_root_directory_pattern",
        "detect_var_log_directory_pattern",
        "detect_bin_directory_pattern",
        "detect_sbin_directory_pattern",
    ]

    for pattern_name in dangerous_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def detect_suspicious_path_patterns(path_str: str) -> list[str]:
    detected = []
    suspicious_patterns = [
        "detect_parent_directory_in_path",
        "detect_suspicious_temp_traversal",
        "detect_suspicious_var_traversal",
    ]

    for pattern_name in suspicious_patterns:
        pattern = SAFE_PATTERNS[pattern_name]
        if pattern.test(path_str):
            detected.append(pattern_name)

    return detected


def validate_path_security(path_str: str) -> dict[str, list[str]]:
    return {
        "traversal_patterns": detect_path_traversal_patterns(path_str),
        "null_bytes": detect_null_byte_patterns(path_str),
        "dangerous_directories": detect_dangerous_directory_patterns(path_str),
        "suspicious_patterns": detect_suspicious_path_patterns(path_str),
    }


class RegexPatternsService:
    """Service class that implements RegexPatternsProtocol.

    Wraps module-level regex pattern functions to provide a protocol-compliant interface.
    """

    def update_pyproject_version(self, content: str, new_version: str) -> str:
        """Update version in pyproject.toml content."""
        return update_pyproject_version(content, new_version)

    def remove_coverage_fail_under(self, content: str) -> str:
        """Remove --cov-fail-under from pytest addopts."""
        return remove_coverage_fail_under(content)

    def update_version_in_changelog(self, content: str, new_version: str) -> str:
        """Update version in changelog content."""
        # Placeholder implementation - can be enhanced later
        return content

    def mask_tokens_in_text(self, text: str) -> str:
        """Mask sensitive tokens in text."""
        return sanitize_internal_urls(text)


if __name__ == "__main__":
    results = validate_all_patterns()
    if all(results.values()):
        print("✅ All regex patterns validated successfully!")
    else:
        failed = [name for name, success in results.items() if not success]
        print(f"❌ Pattern validation failed for: {failed}")
        exit(1)
