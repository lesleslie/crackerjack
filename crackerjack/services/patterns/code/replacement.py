"""Code pattern descriptions."""

from ..core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
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
}
