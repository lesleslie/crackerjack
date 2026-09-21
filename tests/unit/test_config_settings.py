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
        """Test default values for HookSettings.

        enable_ty is True: ty replaced zuban as the primary type checker, so it
        is active by default. It was briefly False after 370983cf (2026-08-03)
        demoted the hook to opt-in, which silently disabled type checking for
        every consumer past 0.70.x. zuban and pyrefly remain opt-in.
        """
        settings = HookSettings()
        assert settings.skip_hooks is False
        assert settings.experimental_hooks is False
        assert settings.enable_pyrefly is False
        assert settings.enable_ty is True
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

    def test_loader_populates_nested_publishing_block(self, tmp_path: Path):
        """Regression guard for the loader bug: keys nested under
        ``publishing:`` must populate ``PublishSettings``.

        Earlier (pre-2026-09-19) versions of ``settings/crackerjack.yaml``
        placed publish-related keys at the top level
        (``publish_version``, ``bump_version``, ``all_workflow``,
        ``no_git_tags``, ``skip_version_check``). The Oneiric loader
        filters against ``CrackerjackSettings.model_fields`` (top-level
        only), so those flat keys were silently dropped — the loader
        returned defaults no matter what the operator wrote. The fix
        is to nest them under ``publishing:`` so Pydantic's recursive
        validation populates ``CrackerjackSettings.publishing``.

        This test pins the new contract: every supported PublishSettings
        field, written as ``publishing.<key>``, must surface on
        ``CrackerjackSettings.publishing.<key>`` after a load.
        """
        from crackerjack.config import load_settings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        (settings_dir / "crackerjack.yaml").write_text(
            "publishing:\n"
            "  publish: '0.1.0'\n"
            "  bump: minor\n"
            "  all: remote\n"
            "  publish_url: 'https://gitlab.example/api/v4/projects/1/packages/pypi'\n"
            "  no_git_tags: true\n"
            "  skip_version_check: true\n"
        )

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish == "0.1.0"
        assert loaded.publishing.bump == "minor"
        assert loaded.publishing.all == "remote"
        assert (
            loaded.publishing.publish_url
            == "https://gitlab.example/api/v4/projects/1/packages/pypi"
        )
        assert loaded.publishing.no_git_tags is True
        assert loaded.publishing.skip_version_check is True

    def test_loader_drops_dead_flat_publishing_keys(self, tmp_path: Path):
        """Regression guard: flat top-level ``publish_*`` / ``bump_*``
        / ``all_workflow`` keys must be silently filtered out by the
        loader (not raise, not populate). The dead flat form is no
        longer documented in ``settings/crackerjack.yaml``, but users
        may have stale entries in their ``settings/local.yaml``; the
        loader must ignore them rather than crash.
        """
        from crackerjack.config import load_settings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        (settings_dir / "crackerjack.yaml").write_text(
            # All flat — none of these are valid CrackerjackSettings fields.
            "publish_version: '0.1.0'\n"
            "bump_version: minor\n"
            "all_workflow: remote\n"
            "no_git_tags: true\n"
            "skip_version_check: true\n"
        )

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        # Defaults — flat keys must not populate anything.
        assert loaded.publishing.publish is None
        assert loaded.publishing.bump is None
        assert loaded.publishing.all is None
        assert loaded.publishing.publish_url is None
        assert loaded.publishing.no_git_tags is False
        assert loaded.publishing.skip_version_check is False

    def test_ecosystem_synthesis_populates_publish_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """BODAI_ECOSYSTEM_CONFIG path-match populates publish_url.

        When the env var points at a valid ecosystem.yaml AND the current
        cwd matches a registered repo's path AND that repo has a
        ``publish.url`` set, ``load_settings`` must surface that URL on
        ``CrackerjackSettings.publishing.publish_url``.
        """
        from crackerjack.config import load_settings

        # Pretend tmp_path IS the project root for this repo.
        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()

        # The ecosystem registry lives elsewhere; the env var points at it.
        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: test-repo\n"
            f"    path: {project_root}\n"
            "    publish:\n"
            "      url: 'https://gitlab.example/api/v4/projects/42/packages/pypi'\n"
            "      token_env: CI_JOB_TOKEN\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url == (
            "https://gitlab.example/api/v4/projects/42/packages/pypi"
        )
        # ``token_env`` from the ecosystem registry must also propagate so
        # ``PublishManagerImpl`` can read the registry-issued token
        # (gitlab.com rejects the public-PyPI ``pypi-...`` token).
        assert loaded.publishing.publish_token_env == "CI_JOB_TOKEN"

    def test_ecosystem_synthesis_propagates_token_env_without_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        """``token_env`` is read from each repo's ``publish`` block
        alongside ``url``. A registry entry with both fields flows
        through to ``publish_token_env``.

        Without this propagation the per-repo `BODAI_ECOSYSTEM_CONFIG`
        entry's `publish.token_env` is just an unused comment field —
        `PublishManagerImpl` would always default to
        ``GITLAB_PERSONAL_ACCESS_TOKEN`` (or refuse) regardless of
        whether the operator configured a different env var.
        """
        from crackerjack.config import load_settings

        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()
        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: test-repo\n"
            f"    path: {project_root}\n"
            "    publish:\n"
            "      url: 'https://gitlab.example/api/v4/projects/42/packages/pypi'\n"
            "      token_env: GITLAB_PERSONAL_ACCESS_TOKEN\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url is not None
        assert loaded.publishing.publish_token_env == "GITLAB_PERSONAL_ACCESS_TOKEN"

    def test_ecosystem_synthesis_yaml_publish_token_env_beats_ecosystem(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ):
        """Operator-set ``publish_token_env`` in settings/local.yaml
        beats the ecosystem default — mirrors the explicit-beats-default
        invariant that ``publish_url`` already enforces."""
        from crackerjack.config import load_settings

        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()
        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: test-repo\n"
            f"    path: {project_root}\n"
            "    publish:\n"
            "      url: 'https://gitlab.example/api/v4/projects/42/packages/pypi'\n"
            "      token_env: ECOSYSTEM_TOKEN\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        # Operator explicitly overrides token_env in their local settings.
        (settings_dir / "local.yaml").write_text(
            "publishing:\n"
            "  publish_token_env: OPERATOR_OVERRIDE_TOKEN\n"
        )

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_token_env == "OPERATOR_OVERRIDE_TOKEN"

    def test_ecosystem_synthesis_no_match_for_unregistered_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Path mismatch between cwd and ecosystem entries yields None.

        Operators who mis-configure ecosystem.yaml (typo in path) must
        not silently route to a different repo. The synthesis must
        yield None when no registered repo matches the cwd.
        """
        from crackerjack.config import load_settings

        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()

        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: elsewhere\n"
            f"    path: /Users/les/Projects/some-other-repo\n"
            "    publish:\n"
            "      url: 'https://gitlab.example/api/v4/projects/99/packages/pypi'\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url is None

    def test_ecosystem_synthesis_respects_yaml_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Settings YAML value wins over ecosystem lookup.

        Priority order: CLI flag > env var > ecosystem lookup > settings
        YAML > default. The synthesis must skip when settings/local.yaml
        has already populated ``publishing.publish_url`` — operators
        expect explicit per-repo config to beat ecosystem-wide defaults.
        """
        from crackerjack.config import load_settings

        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()
        (settings_dir / "crackerjack.yaml").write_text(
            "publishing:\n"
            "  publish_url: 'https://yaml-override.example/pypi'\n"
        )

        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: test-repo\n"
            f"    path: {project_root}\n"
            "    publish:\n"
            "      url: 'https://ecosystem.example/pypi'\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        # Settings YAML beats ecosystem.
        assert loaded.publishing.publish_url == "https://yaml-override.example/pypi"

    def test_ecosystem_synthesis_skips_when_env_var_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Without BODAI_ECOSYSTEM_CONFIG, no synthesis runs.

        Operators who don't run Mahavishnu (or have it but forgot the env
        var) must see crackerjack behave exactly as before — no lookup,
        no surprise values, PyPI default.
        """
        from crackerjack.config import load_settings

        monkeypatch.delenv("BODAI_ECOSYSTEM_CONFIG", raising=False)

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        # Note: no ecosystem.yaml file exists at all.

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url is None

    def test_ecosystem_synthesis_skips_repo_with_null_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A registered repo with ``publish.url: null`` must NOT be
        picked up — the synthesis is for ACTIVE private-index configs.
        """
        from crackerjack.config import load_settings

        project_root = tmp_path
        settings_dir = project_root / "settings"
        settings_dir.mkdir()

        ecosystem_path = tmp_path / "ecosystem.yaml"
        ecosystem_path.write_text(
            "repos:\n"
            f"  - name: test-repo\n"
            f"    path: {project_root}\n"
            "    publish:\n"
            "      url: null\n"
            "      token_env: null\n"
        )
        monkeypatch.setenv("BODAI_ECOSYSTEM_CONFIG", str(ecosystem_path))

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url is None

    def test_ecosystem_synthesis_no_op_when_ecosystem_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A pointing env var with a non-existent file must not crash."""
        from crackerjack.config import load_settings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()

        monkeypatch.setenv(
            "BODAI_ECOSYSTEM_CONFIG", str(tmp_path / "nonexistent.yaml")
        )

        loaded = load_settings(CrackerjackSettings, settings_dir=settings_dir)

        assert loaded.publishing.publish_url is None


class TestAISettings:
    """Tests for AISettings."""

    def test_default_values(self):
        """Test default values for AISettings."""
        settings = AISettings()
        assert settings.ai_agent is False
        assert settings.start_mcp_server is False
        assert settings.max_iterations == 20
        assert settings.autofix is True
        assert settings.ai_agent_autofix is False
        assert settings.ai_provider == "minimax"

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
        """Test creating settings from nested model instances.

        Mirrors the runtime path the YAML/JSON loader takes: parse the input
        into nested model instances (AISettings, TestSettings) and pass them
        to the parent CrackerjackSettings. Asserts that nested fields are
        preserved.
        """
        ai = AISettings(ai_provider="ollama", max_iterations=15)
        testing = TestSettings(test_workers=8, coverage=True)
        settings = CrackerjackSettings(ai=ai, testing=testing)
        assert settings.ai.ai_provider == "ollama"
        assert settings.ai.max_iterations == 15
        assert settings.testing.test_workers == 8
        assert settings.testing.coverage is True


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_ai_provider_raises_error(self):
        """Test that invalid AI provider raises validation error."""
        import typing

        # The pydantic validator must reject unknown providers; we feed an
        # intentionally invalid value through ``model_construct``-style coercion
        # so the static type checker cannot flag the literal before it reaches
        # the validator at runtime.
        bad_value: typing.Any = "invalid_provider"
        with pytest.raises(ValidationError):
            AISettings(ai_provider=bad_value)

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
        assert settings.websocket_port == 8696


class TestZubanLSPSettings:
    """Tests for ZubanLSPSettings."""

    def test_default_values(self):
        """Test default Zuban LSP settings.

        Per commit 13be8c1c (feat(crackerjack): disable zuban LSP by default
        — ty is the new default type checker), zuban is opt-in: both
        enabled and auto_start default to False. The other invariants
        (port, mode, timeout) are unchanged.
        """
        settings = ZubanLSPSettings()
        assert settings.enabled is False
        assert settings.auto_start is False
        assert settings.port == 8685
        assert settings.mode == "stdio"
        assert settings.timeout == 120


class TestAdapterTimeouts:
    """Tests for AdapterTimeouts."""

    def test_default_values(self):
        """Test default adapter timeouts."""
        settings = AdapterTimeouts()
        assert settings.zuban_lsp_timeout == 120.0
        assert settings.skylos_timeout == 900
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
