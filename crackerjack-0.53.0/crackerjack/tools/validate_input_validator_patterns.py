import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crackerjack.services.input_validator import SecureInputValidator
from crackerjack.services.regex_patterns import SAFE_PATTERNS


def test_sql_injection_patterns() -> bool:
    test_cases = [
        ("SELECT * FROM users", True, "Basic SELECT"),
        ("UNION SELECT password FROM admin", True, "UNION injection"),
        ("'; DROP TABLE users; --", True, "SQL comment injection"),
        ("' OR 1=1--", True, "Boolean injection"),
        ("xp_cmdshell('dir')", True, "SQL Server specific"),
        ("sp_executesql @sql", True, "SQL Server procedure"),
        ("user selected item", False, "Legitimate text with 'select'"),
        ("button execution", False, "Legitimate text with 'execution'"),
        ("team membership", False, "Legitimate text without SQL keywords"),
        ("normal text", False, "Normal text"),
    ]

    patterns = [
        "validate_sql_injection_patterns",
        "validate_sql_comment_patterns",
        "validate_sql_boolean_injection",
        "validate_sql_server_specific",
    ]

    for text, should_detect, _description in test_cases:
        detected = False
        for pattern_name in patterns:
            if SAFE_PATTERNS[pattern_name].test(text):
                detected = True
                break

        if detected != should_detect:
            return False

    return True


def test_code_injection_patterns() -> bool:
    test_cases = [
        ("eval(user_input)", True, "eval() execution"),
        ("exec(malicious_code)", True, "exec() execution"),
        ("__import__('os')", True, "Dynamic import"),
        ("getattr(obj, 'dangerous')", True, "Dynamic attribute access"),
        ("subprocess.run(cmd)", True, "System command"),
        ("os.system('rm -rf')", True, "OS system call"),
        ("compile(code, 'string', 'exec')", True, "Code compilation"),
        ("evaluate the results", False, "Legitimate text with 'eval'"),
        ("execute the plan", False, "Legitimate text with 'execute'"),
        ("import statement", False, "Normal import discussion"),
        ("compiled successfully", False, "Normal compilation discussion"),
    ]

    patterns = [
        "validate_code_eval_injection",
        "validate_code_dynamic_access",
        "validate_code_system_commands",
        "validate_code_compilation",
    ]

    for text, should_detect, _description in test_cases:
        detected = False
        for pattern_name in patterns:
            if SAFE_PATTERNS[pattern_name].test(text):
                detected = True
                break

        if detected != should_detect:
            return False

    return True


def test_job_id_validation() -> bool:
    test_cases = [
        ("valid_job-123", True, "Standard job ID"),
        ("another-valid_job", True, "Hyphen and underscore"),
        ("JOB123", True, "Uppercase"),
        ("job_456", True, "Underscore only"),
        ("job-789", True, "Hyphen only"),
        ("complex_job-id_123", True, "Complex valid ID"),
        ("job with spaces", False, "Contains spaces"),
        ("job@invalid", False, "Contains @ symbol"),
        ("job.invalid", False, "Contains dot"),
        ("job/invalid", False, "Contains slash"),
        ("job=invalid", False, "Contains equals"),
        ("job$invalid", False, "Contains dollar"),
        ("", False, "Empty string"),
    ]

    pattern = SAFE_PATTERNS["validate_job_id_format"]

    for job_id, should_be_valid, _description in test_cases:
        is_valid = pattern.test(job_id)

        if is_valid != should_be_valid:
            return False

    return True


def test_env_var_validation() -> bool:
    test_cases = [
        ("VALID_VAR", True, "Standard env var"),
        ("_PRIVATE_VAR", True, "Starting with underscore"),
        ("API_KEY_123", True, "With numbers"),
        ("DATABASE_URL", True, "Typical env var"),
        ("MAX_RETRIES", True, "Another typical var"),
        ("lowercase_var", False, "Contains lowercase"),
        ("123_INVALID", False, "Starts with number"),
        ("INVALID-VAR", False, "Contains hyphen"),
        ("INVALID.VAR", False, "Contains dot"),
        ("INVALID VAR", False, "Contains space"),
        ("INVALID@VAR", False, "Contains @ symbol"),
        ("", False, "Empty string"),
    ]

    pattern = SAFE_PATTERNS["validate_env_var_name_format"]

    for env_var, should_be_valid, _description in test_cases:
        is_valid = pattern.test(env_var)

        if is_valid != should_be_valid:
            return False

    return True


def test_integration_with_validator() -> bool:
    validator = SecureInputValidator()

    result = validator.sanitizer.sanitize_string("'; DROP TABLE users; --")
    if result.valid:
        return False

    result = validator.validate_job_id("valid_job-123")
    if not result.valid:
        return False

    result = validator.validate_job_id("invalid job with spaces")
    if result.valid:
        return False

    result = validator.validate_environment_var("VALID_VAR", "some_value")
    if not result.valid:
        return False

    result = validator.validate_environment_var("invalid_var", "some_value")
    return not result.valid


def main() -> int:
    tests = [
        test_sql_injection_patterns,
        test_code_injection_patterns,
        test_job_id_validation,
        test_env_var_validation,
        test_integration_with_validator,
    ]

    all_passed = True
    for test_func in tests:
        if not test_func():
            all_passed = False

    if all_passed:
        print("ALL SECURITY VALIDATION TESTS PASSED")
        return 0
    else:
        print("SECURITY VALIDATION TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
