"""Path traversal and directory access detection patterns.

This module contains patterns for detecting directory traversal attacks,
suspicious file path patterns, and unauthorized directory access attempts.
"""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
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
}
