"""Input validation patterns."""

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
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
}
