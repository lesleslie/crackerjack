"""Unsafe operation detection and remediation patterns.

This module contains patterns for detecting and fixing unsafe operations
including weak cryptography, insecure random usage, subprocess shell injection,
and other dangerous programming practices.
"""

import re

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
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
    "detect_insecure_random_usage": ValidatedPattern(
        name="detect_insecure_random_usage",
        pattern=r"\brandom\.(?:random|choice)\([^)]*\)",
        replacement="[INSECURE_RANDOM]()",
        description="Detect insecure random module usage for security-sensitive"
        " operations",
        global_replace=True,
        test_cases=[
            ("random.random()", "[INSECURE_RANDOM]()"),
            ("random.choice(items)", "[INSECURE_RANDOM]()"),
            ("secrets.choice(items)", "secrets.choice(items)"),
            ("my_random.choice()", "my_random.choice()"),
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
}
