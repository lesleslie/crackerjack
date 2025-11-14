"""Code injection detection patterns for SQL, Python, and system commands.

This module contains patterns for detecting SQL injection, code evaluation
injection, dynamic code execution, and system command injection attacks.
"""

import re

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
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
}
