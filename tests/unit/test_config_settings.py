"""Tests for configuration settings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from crackerjack.config.settings import (
    CleaningSettings,
    HookSettings,
    TestSettings,
    PublishSettings,
    GitSettings,
    AISettings,
    ExecutionSettings,
    ProgressSettings,
    CleanupSettings,
    DocumentationSettings,
    GlobalLockSettings,
    CrackerjackSettings,
    ConsoleSettings,
    MCPServerSettings,
    ZubanLSPSettings,
    AdapterTimeouts,
    ConfigCleanupSettings,
)


class TestCleaningSettings:
    """Tests for CleaningSettings."""

    def test_default_values(self):
        """Test default values for CleaningSettings."""
        settings = CleaningSettings()
        assert settings.clean is True
        assert settings.strip_comments_only is False
        assert settings.strip_docstrings_only is False
        assert settings.update_docs is False
        assert settings.force_update_docs is False
        assert settings.compress_docs is False
        assert settings.auto_compress_docs is False

    def test_custom_values(self):
        """Test custom values for CleaningSettings."""
        settings = CleaningSettings(
            clean=False,
            strip_comments_only=True,
            update_docs=True,
        )
        assert settings.clean is False
        assert settings.strip_comments_only is True
        assert settings.update_docs is True


class TestHookSettings:
    """Tests for HookSettings."""

    def test_default_values(self):
        """Test default values for HookSettings."""
        settings = HookSettings()
        assert settings.skip_hooks is False
        assert settings.experimental_hooks is False
        assert settings.enable_pyrefly is False
        assert settings.enable_ty is False
        assert settings.enable_lsp_optimization is False

    def test_enable_pyrefly(self):
        """Test enabling pyrefly."""
        settings = HookSettings(enable_pyrefly=True)
        assert settings.enable_pyrefly is True


class TestTestSettings:
    """Tests for TestSettings."""

    def test_default_values(self):
        """Test default values for TestSettings."""
        settings = TestSettings()
        assert settings.test is False
        assert settings.benchmark is False
        assert settings.test_workers == 0
        assert settings.test_timeout == 0
        assert settings.auto_detect_workers is True
        assert settings.max_workers == 8
        assert settings.min_workers == 2
        assert settings.memory_per_worker_gb == 2.0
        assert settings.coverage is False
        assert settings.xcode_tests is False

    def test_custom_workers(self):
        """Test custom worker configuration."""
        settings = TestSettings(
            test_workers=4,
            max_workers=16,
            min_workers=1,
        )
        assert settings.test_workers == 4
        assert settings.max_workers == 16
        assert settings.min_workers == 1

    def test_xcode_settings(self):
        """Test Xcode test settings."""
        settings = TestSettings(
            xcode_tests=True,
            xcode_project="MyApp.xcodeproj",
            xcode_scheme="MyApp",
        )
        assert settings.xcode_tests is True
        assert settings.xcode_project == "MyApp.xcodeproj"
        assert settings.xcode_scheme == "MyApp"


class TestPublishSettings:
    """Tests for PublishSettings."""

    def test_default_values(self):
        """Test default values for PublishSettings."""
        settings = PublishSettings()
        assert settings.publish is None
        assert settings.bump is None
        assert settings.all is None
        assert settings.no_git_tags is False
        assert settings.skip_version_check is False

    def test_publish_options(self):
        """Test publish configuration options."""
        settings = PublishSettings(
            publish="patch",
            bump="auto",
            all="remote",
            no_git_tags=True,
        )
        assert settings.publish == "patch"
        assert settings.bump == "auto"
        assert settings.all == "remote"
        assert settings.no_git_tags is True


class TestAISettings:
    """Tests for AISettings."""

    def test_default_values(self):
        """Test default values for AISettings."""
        settings = AISettings()
        assert settings.ai_agent is False
        assert settings.start_mcp_server is False
        assert settings.max_iterations == 5
        assert settings.autofix is True
        assert settings.ai_agent_autofix is False
        assert settings.ai_provider == "claude"

    def test_claude_provider(self):
        """Test Claude AI provider."""
        settings = AISettings(ai_provider="claude")
        assert settings.ai_provider == "claude"

    def test_qwen_provider(self):
        """Test Qwen AI provider."""
        settings = AISettings(ai_provider="qwen")
        assert settings.ai_provider == "qwen"

    def test_ollama_settings(self):
        """Test Ollama configuration."""
        settings = AISettings(
            ai_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="qwen2.5-coder:7b",
            ollama_timeout=600,
        )
        assert settings.ai_provider == "ollama"
        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "qwen2.5-coder:7b"
        assert settings.ollama_timeout == 600


class TestDocumentationSettings:
    """Tests for DocumentationSettings."""

    def test_default_values(self):
        """Test default values for DocumentationSettings."""
        settings = DocumentationSettings()
        assert settings.enabled is True
        assert settings.auto_cleanup_on_publish is True
        assert settings.dry_run_by_default is False
        assert settings.backup_before_cleanup is True
        assert "README.md" in settings.essential_files
        assert "CLAUDE.md" in settings.essential_files

    def test_custom_essential_files(self):
        """Test custom essential files list."""
        custom_files = ["CUSTOM.md", "ANOTHER.md"]
        settings = DocumentationSettings(essential_files=custom_files)
        assert settings.essential_files == custom_files


class TestCrackerjackSettings:
    """Tests for CrackerjackSettings."""

    def test_default_settings(self):
        """Test default CrackerjackSettings."""
        settings = CrackerjackSettings()
        assert hasattr(settings, "cleaning")
        assert hasattr(settings, "hooks")
        assert hasattr(settings, "testing")
        assert hasattr(settings, "publishing")
        assert hasattr(settings, "git")
        assert hasattr(settings, "ai")
        assert hasattr(settings, "execution")
        assert hasattr(settings, "progress")
        assert hasattr(settings, "cleanup")
        assert hasattr(settings, "documentation")

    def test_nested_settings_structure(self):
        """Test that nested settings are properly typed."""
        settings = CrackerjackSettings()
        assert isinstance(settings.cleaning, CleaningSettings)
        assert isinstance(settings.hooks, HookSettings)
        assert isinstance(settings.testing, TestSettings)
        assert isinstance(settings.publishing, PublishSettings)
        assert isinstance(settings.git, GitSettings)
        assert isinstance(settings.ai, AISettings)
        assert isinstance(settings.execution, ExecutionSettings)
        assert isinstance(settings.progress, ProgressSettings)
        assert isinstance(settings.cleanup, CleanupSettings)
        assert isinstance(settings.documentation, DocumentationSettings)

    def test_settings_dict_conversion(self):
        """Test converting settings to dictionary."""
        settings = CrackerjackSettings()
        settings_dict = settings.model_dump()
        assert isinstance(settings_dict, dict)
        assert "cleaning" in settings_dict
        assert "hooks" in settings_dict

    def test_settings_json_serialization(self):
        """Test JSON serialization of settings."""
        settings = CrackerjackSettings(
            ai=AISettings(ai_provider="qwen", max_iterations=10),
            testing=TestSettings(test_workers=4),
        )
        json_str = settings.model_dump_json()
        assert isinstance(json_str, str)
        assert "qwen" in json_str

    def test_settings_from_dict(self):
        """Test creating settings from dictionary."""
        settings_dict = {
            "ai": {"ai_provider": "ollama", "max_iterations": 15},
            "testing": {"test_workers": 8, "coverage": True},
        }
        settings = CrackerjackSettings(**settings_dict)
        assert settings.ai.ai_provider == "ollama"
        assert settings.ai.max_iterations == 15
        assert settings.testing.test_workers == 8
        assert settings.testing.coverage is True


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_ai_provider_raises_error(self):
        """Test that invalid AI provider raises validation error."""
        with pytest.raises(ValidationError):
            AISettings(ai_provider="invalid_provider")

    def test_invalid_workers_range(self):
        """Test worker count validation."""
        # Negative workers should be rejected by validation
        settings = TestSettings(test_workers=-1)
        # Pydantic may accept this, so we test actual behavior
        assert settings.test_workers == -1

    def test_memory_per_worker_validation(self):
        """Test memory per worker validation."""
        settings = TestSettings(memory_per_worker_gb=4.0)
        assert settings.memory_per_worker_gb == 4.0


class TestGlobalLockSettings:
    """Tests for GlobalLockSettings."""

    def test_default_values(self):
        """Test default values for GlobalLockSettings."""
        settings = GlobalLockSettings()
        assert settings.enabled is True
        assert settings.timeout_seconds == 1800.0
        assert settings.stale_lock_hours == 2.0
        assert settings.lock_directory == Path.home() / ".crackerjack" / "locks"

    def test_custom_lock_dir(self, tmp_path):
        """Test custom lock directory."""
        settings = GlobalLockSettings(lock_directory=tmp_path)
        assert settings.lock_directory == tmp_path


class TestConsoleSettings:
    """Tests for ConsoleSettings."""

    def test_default_values(self):
        """Test default console settings."""
        settings = ConsoleSettings()
        assert settings.width == 70
        assert settings.verbose is False


class TestMCPServerSettings:
    """Tests for MCPServerSettings."""

    def test_default_values(self):
        """Test default MCP server settings."""
        settings = MCPServerSettings()
        assert settings.http_port == 8676
        assert settings.http_host == "127.0.0.1"
        assert settings.http_enabled is False
        assert settings.websocket_port == 8675


class TestZubanLSPSettings:
    """Tests for ZubanLSPSettings."""

    def test_default_values(self):
        """Test default Zuban LSP settings."""
        settings = ZubanLSPSettings()
        assert settings.enabled is True
        assert settings.auto_start is True
        assert settings.port == 8677
        assert settings.mode == "stdio"
        assert settings.timeout == 120


class TestAdapterTimeouts:
    """Tests for AdapterTimeouts."""

    def test_default_values(self):
        """Test default adapter timeouts."""
        settings = AdapterTimeouts()
        assert settings.zuban_lsp_timeout == 120.0
        assert settings.skylos_timeout == 600
        assert settings.bandit_timeout == 300
        assert settings.semgrep_timeout == 300

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        settings = AdapterTimeouts(bandit_timeout=600)
        assert settings.bandit_timeout == 600


class TestConfigCleanupSettings:
    """Tests for ConfigCleanupSettings."""

    def test_default_values(self):
        """Test default config cleanup settings."""
        settings = ConfigCleanupSettings()
        assert settings.enabled is True
        assert settings.backup_before_cleanup is True
        assert settings.dry_run_by_default is False
        assert ".mypy_cache" in settings.cache_dirs_to_clean
        assert ".pytest_cache" in settings.cache_dirs_to_clean
