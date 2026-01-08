from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class CrackerjackSettings(BaseSettings):
    server_name: str = Field(
        default="Crackerjack QA Server", description="Server display name"
    )
    server_description: str = Field(
        default="Python QA tooling with AI integration",
        description="Server description",
    )
    instance_id: str | None = Field(
        default=None, description="Unique server instance ID for multi-instance support"
    )
    runtime_dir: Path = Field(
        default=Path.home() / ".crackerjack", description="Runtime cache directory"
    )

    qa_mode: bool = Field(default=False, description="Enable QA analysis mode")
    test_suite_path: Path = Field(
        default=Path("tests"), description="Test suite directory path"
    )
    auto_fix: bool = Field(default=False, description="Enable automatic issue fixing")
    ai_agent: bool = Field(
        default=False, description="Enable AI-powered code analysis agent"
    )

    ruff_enabled: bool = Field(default=True, description="Enable Ruff linter/formatter")
    bandit_enabled: bool = Field(
        default=True, description="Enable Bandit security scanner"
    )
    semgrep_enabled: bool = Field(default=False, description="Enable Semgrep SAST")
    mypy_enabled: bool = Field(default=True, description="Enable mypy type checking")
    zuban_enabled: bool = Field(
        default=True, description="Enable Zuban ultra-fast type checker"
    )
    skylos_enabled: bool = Field(
        default=True, description="Enable Skylos dead code detection"
    )
    pyright_enabled: bool = Field(
        default=False, description="Enable Pyright type checking"
    )
    gitleaks_enabled: bool = Field(
        default=False, description="Enable Gitleaks secret detection"
    )
    pip_audit_enabled: bool = Field(
        default=True, description="Enable pip-audit dependency scanning"
    )

    max_parallel_hooks: int = Field(
        default=4, description="Maximum parallel pre-commit hooks"
    )
    test_workers: int = Field(default=0, description="Pytest workers (0=auto-detect)")
    test_timeout: int = Field(default=300, description="Test timeout in seconds")
    auto_detect_workers: bool = Field(
        default=True, description="Automatically detect optimal worker count"
    )
    max_workers: int = Field(default=8, description="Maximum number of test workers")
    min_workers: int = Field(default=2, description="Minimum number of test workers")
    memory_per_worker_gb: float = Field(
        default=2.0, description="Memory per worker in GB for worker calculation"
    )

    verbose: bool = Field(default=False, description="Enable verbose logging")
    interactive: bool = Field(default=False, description="Enable interactive mode")
    async_mode: bool = Field(
        default=False, description="Enable async workflow execution"
    )
    enable_orchestration: bool = Field(
        default=True, description="Enable workflow orchestration"
    )

    skip_hooks: bool = Field(default=False, description="Skip hook execution")
    experimental_hooks: bool = Field(
        default=False, description="Enable experimental hooks"
    )

    auto_cleanup: bool = Field(
        default=True, description="Automatically clean up temp files"
    )
    keep_debug_logs: int = Field(
        default=5, description="Number of debug logs to retain"
    )
    keep_coverage_files: int = Field(
        default=10, description="Number of coverage files to retain"
    )

    http_port: int = Field(default=8676, description="MCP HTTP server port")
    http_host: str = Field(default="127.0.0.1", description="MCP HTTP server host")
    http_enabled: bool = Field(default=False, description="Enable MCP HTTP server")

    zuban_lsp_enabled: bool = Field(
        default=True, description="Enable Zuban LSP integration"
    )
    zuban_lsp_auto_start: bool = Field(
        default=True, description="Auto-start Zuban LSP server"
    )
    zuban_lsp_port: int = Field(default=8677, description="Zuban LSP server port")
    zuban_lsp_timeout: int = Field(
        default=120, description="Zuban LSP timeout in seconds"
    )

    global_lock_enabled: bool = Field(
        default=True, description="Enable global lock mechanism"
    )
    global_lock_timeout_seconds: float = Field(
        default=1800.0, description="Global lock timeout"
    )
    global_lock_stale_hours: float = Field(
        default=2.0, description="Hours before lock is considered stale"
    )

    class Config:
        env_prefix = "CRACKERJACK_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def load(cls, config_name: str = "crackerjack") -> "CrackerjackSettings":
        return cls()
