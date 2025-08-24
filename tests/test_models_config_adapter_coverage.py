"""Tests for models.config_adapter module to increase coverage significantly.
Targeting 68% → 85%+ coverage (~20 statements).
"""

from unittest.mock import Mock

import pytest

from crackerjack.models.config import WorkflowOptions
from crackerjack.models.config_adapter import LegacyOptionsWrapper, OptionsAdapter
from crackerjack.models.protocols import OptionsProtocol


class TestOptionsAdapter:
    """Test OptionsAdapter static methods."""

    @pytest.fixture
    def mock_options(self):
        """Create a comprehensive mock OptionsProtocol object."""
        options = Mock(spec=OptionsProtocol)

        # Cleaning options
        options.clean = True
        options.update_docs = False
        options.force_update_docs = True
        options.compress_docs = False
        options.auto_compress_docs = True

        # Hook options
        options.skip_hooks = False
        options.update_precommit = True
        options.experimental_hooks = False
        options.enable_pyrefly = True
        options.enable_ty = False

        # Testing options
        options.test = True
        options.benchmark = False
        options.benchmark_regression = True
        options.benchmark_regression_threshold = 0.2
        options.test_workers = 4
        options.test_timeout = 300

        # Publishing options
        options.publish = "patch"
        options.bump = "minor"
        options.all = "major"
        options.cleanup_pypi = True
        options.keep_releases = 5
        options.no_git_tags = False
        options.skip_version_check = True

        # Git options
        options.commit = True
        options.create_pr = False

        # AI options
        options.ai_agent = True
        options.start_mcp_server = False

        # Execution options
        options.interactive = False
        options.verbose = True
        options.async_mode = False
        options.no_config_updates = True

        # Progress options
        options.track_progress = True
        options.resume_from = "session123"
        options.progress_file = "progress.json"

        return options

    @pytest.fixture
    def minimal_options(self):
        """Create a minimal mock OptionsProtocol object with missing attributes."""

        # Create simple object without the problematic Mock behavior
        class MinimalOptions:
            def __init__(self) -> None:
                self.clean = False
                self.test = True
                self.verbose = False

        return MinimalOptions()

    def test_from_options_protocol_comprehensive(self, mock_options) -> None:
        """Test converting comprehensive OptionsProtocol to WorkflowOptions."""
        workflow_options = OptionsAdapter.from_options_protocol(mock_options)

        # Verify cleaning config
        assert workflow_options.cleaning.clean is True
        assert workflow_options.cleaning.update_docs is False
        assert workflow_options.cleaning.force_update_docs is True
        assert workflow_options.cleaning.compress_docs is False
        assert workflow_options.cleaning.auto_compress_docs is True

        # Verify hooks config
        assert workflow_options.hooks.skip_hooks is False
        assert workflow_options.hooks.update_precommit is True
        assert workflow_options.hooks.experimental_hooks is False
        assert workflow_options.hooks.enable_pyrefly is True
        assert workflow_options.hooks.enable_ty is False

        # Verify testing config
        assert workflow_options.testing.test is True
        assert workflow_options.testing.benchmark is False
        assert workflow_options.testing.benchmark_regression is True
        assert workflow_options.testing.benchmark_regression_threshold == 0.2
        assert workflow_options.testing.test_workers == 4
        assert workflow_options.testing.test_timeout == 300

        # Verify publishing config
        assert workflow_options.publishing.publish == "patch"
        assert workflow_options.publishing.bump == "minor"
        assert workflow_options.publishing.all == "major"
        assert workflow_options.publishing.cleanup_pypi is True
        assert workflow_options.publishing.keep_releases == 5
        assert workflow_options.publishing.no_git_tags is False
        assert workflow_options.publishing.skip_version_check is True

        # Verify git config
        assert workflow_options.git.commit is True
        assert workflow_options.git.create_pr is False

        # Verify AI config
        assert workflow_options.ai.ai_agent is True
        assert workflow_options.ai.start_mcp_server is False

        # Verify execution config
        assert workflow_options.execution.interactive is False
        assert workflow_options.execution.verbose is True
        assert workflow_options.execution.async_mode is False
        assert workflow_options.execution.no_config_updates is True

        # Verify progress config
        assert workflow_options.progress.track_progress is True
        assert workflow_options.progress.resume_from == "session123"
        assert workflow_options.progress.progress_file == "progress.json"

    def test_from_options_protocol_with_defaults(self, minimal_options) -> None:
        """Test converting OptionsProtocol with missing attributes uses defaults."""
        workflow_options = OptionsAdapter.from_options_protocol(minimal_options)

        # Test that missing attributes use default values
        assert workflow_options.cleaning.clean is False  # From mock
        assert workflow_options.cleaning.update_docs is False  # Default
        assert workflow_options.cleaning.force_update_docs is False  # Default
        assert workflow_options.cleaning.compress_docs is False  # Default
        assert workflow_options.cleaning.auto_compress_docs is False  # Default

        assert workflow_options.testing.test is True  # From mock
        assert workflow_options.testing.benchmark is False  # Default
        assert workflow_options.testing.benchmark_regression is False  # Default
        assert workflow_options.testing.benchmark_regression_threshold == 0.1  # Default
        assert workflow_options.testing.test_workers == 0  # Default
        assert workflow_options.testing.test_timeout == 0  # Default

        assert workflow_options.execution.verbose is False  # From mock
        assert workflow_options.execution.interactive is False  # Default
        assert workflow_options.execution.async_mode is False  # Default
        assert workflow_options.execution.no_config_updates is False  # Default

    def test_to_options_protocol(self) -> None:
        """Test converting WorkflowOptions to LegacyOptionsWrapper."""
        workflow_options = WorkflowOptions()  # Use defaults

        legacy_wrapper = OptionsAdapter.to_options_protocol(workflow_options)

        assert isinstance(legacy_wrapper, LegacyOptionsWrapper)
        assert legacy_wrapper._options is workflow_options


class TestLegacyOptionsWrapper:
    """Test LegacyOptionsWrapper class."""

    @pytest.fixture
    def workflow_options(self):
        """Create WorkflowOptions with custom values."""
        return WorkflowOptions(
            cleaning=Mock(
                clean=True,
                update_docs=True,
                force_update_docs=False,
                compress_docs=True,
                auto_compress_docs=False,
            ),
            hooks=Mock(
                skip_hooks=True,
                update_precommit=False,
                experimental_hooks=True,
                enable_pyrefly=False,
                enable_ty=True,
            ),
            testing=Mock(
                test=True,
                benchmark=True,
                benchmark_regression=False,
                benchmark_regression_threshold=0.5,
                test_workers=8,
                test_timeout=600,
            ),
            publishing=Mock(
                publish="major",
                bump="patch",
                all="minor",
                cleanup_pypi=False,
                keep_releases=20,
                no_git_tags=True,
                skip_version_check=False,
            ),
            git=Mock(commit=False, create_pr=True),
            ai=Mock(ai_agent=False, start_mcp_server=True),
            execution=Mock(
                interactive=True,
                verbose=False,
                async_mode=True,
                no_config_updates=False,
            ),
            progress=Mock(
                track_progress=False,
                resume_from="test_session",
                progress_file="test_progress.json",
            ),
        )

    @pytest.fixture
    def wrapper(self, workflow_options):
        """Create LegacyOptionsWrapper instance."""
        return LegacyOptionsWrapper(workflow_options)

    def test_wrapper_initialization(self, workflow_options) -> None:
        """Test LegacyOptionsWrapper initialization."""
        wrapper = LegacyOptionsWrapper(workflow_options)
        assert wrapper._options is workflow_options

    def test_git_properties(self, wrapper) -> None:
        """Test git-related properties."""
        assert wrapper.commit is False
        assert wrapper.create_pr is True

    def test_execution_properties(self, wrapper) -> None:
        """Test execution-related properties."""
        assert wrapper.interactive is True
        assert wrapper.verbose is False
        assert wrapper.no_config_updates is False
        assert wrapper.async_mode is True

    def test_cleaning_properties(self, wrapper) -> None:
        """Test cleaning-related properties."""
        assert wrapper.clean is True
        assert wrapper.update_docs is True
        assert wrapper.force_update_docs is False
        assert wrapper.compress_docs is True
        assert wrapper.auto_compress_docs is False

    def test_publishing_properties(self, wrapper) -> None:
        """Test publishing-related properties."""
        assert wrapper.cleanup_pypi is False
        assert wrapper.keep_releases == 20
        assert wrapper.publish == "major"
        assert wrapper.bump == "patch"
        assert wrapper.all == "minor"
        assert wrapper.no_git_tags is True
        assert wrapper.skip_version_check is False

    def test_testing_properties(self, wrapper) -> None:
        """Test testing-related properties."""
        assert wrapper.test is True
        assert wrapper.benchmark is True
        assert wrapper.benchmark_regression is False
        assert wrapper.benchmark_regression_threshold == 0.5
        assert wrapper.test_workers == 8
        assert wrapper.test_timeout == 600

    def test_ai_properties(self, wrapper) -> None:
        """Test AI-related properties."""
        assert wrapper.ai_agent is False
        assert wrapper.start_mcp_server is True

    def test_hooks_properties(self, wrapper) -> None:
        """Test hooks-related properties."""
        assert wrapper.skip_hooks is True
        assert wrapper.update_precommit is False
        assert wrapper.experimental_hooks is True
        assert wrapper.enable_pyrefly is False
        assert wrapper.enable_ty is True

    def test_progress_properties(self, wrapper) -> None:
        """Test progress-related properties."""
        assert wrapper.track_progress is False
        assert wrapper.resume_from == "test_session"
        assert wrapper.progress_file == "test_progress.json"


class TestIntegrationBothDirections:
    """Test integration between both conversion directions."""

    def test_round_trip_conversion(self) -> None:
        """Test converting from OptionsProtocol to WorkflowOptions and back."""
        # Create mock options
        original_options = Mock(spec=OptionsProtocol)
        original_options.clean = True
        original_options.test = False
        original_options.verbose = True
        original_options.commit = False
        original_options.ai_agent = True
        original_options.interactive = False
        original_options.track_progress = True
        original_options.skip_hooks = False
        original_options.benchmark = True
        original_options.publish = "patch"
        original_options.update_docs = False
        original_options.cleanup_pypi = True

        # Convert to WorkflowOptions
        workflow_options = OptionsAdapter.from_options_protocol(original_options)

        # Convert back to legacy wrapper
        legacy_wrapper = OptionsAdapter.to_options_protocol(workflow_options)

        # Verify round-trip preservation
        assert legacy_wrapper.clean == original_options.clean
        assert legacy_wrapper.test == original_options.test
        assert legacy_wrapper.verbose == original_options.verbose
        assert legacy_wrapper.commit == original_options.commit
        assert legacy_wrapper.ai_agent == original_options.ai_agent
        assert legacy_wrapper.interactive == original_options.interactive
        assert legacy_wrapper.track_progress == original_options.track_progress
        assert legacy_wrapper.skip_hooks == original_options.skip_hooks
        assert legacy_wrapper.benchmark == original_options.benchmark
        assert legacy_wrapper.publish == original_options.publish
        assert legacy_wrapper.update_docs == original_options.update_docs
        assert legacy_wrapper.cleanup_pypi == original_options.cleanup_pypi

    def test_complex_options_preservation(self) -> None:
        """Test that complex option values are preserved correctly."""
        original_options = Mock(spec=OptionsProtocol)
        original_options.benchmark_regression_threshold = 0.15
        original_options.test_workers = 12
        original_options.test_timeout = 900
        original_options.keep_releases = 25
        original_options.resume_from = "complex_session_id_123"
        original_options.progress_file = "/path/to/complex/progress.json"

        workflow_options = OptionsAdapter.from_options_protocol(original_options)
        legacy_wrapper = OptionsAdapter.to_options_protocol(workflow_options)

        assert legacy_wrapper.benchmark_regression_threshold == 0.15
        assert legacy_wrapper.test_workers == 12
        assert legacy_wrapper.test_timeout == 900
        assert legacy_wrapper.keep_releases == 25
        assert legacy_wrapper.resume_from == "complex_session_id_123"
        assert legacy_wrapper.progress_file == "/path/to/complex/progress.json"

    def test_none_values_handling(self) -> None:
        """Test handling of None values in options."""
        original_options = Mock(spec=OptionsProtocol)
        original_options.publish = None
        original_options.bump = None
        original_options.all = None
        original_options.resume_from = None
        original_options.progress_file = None

        workflow_options = OptionsAdapter.from_options_protocol(original_options)
        legacy_wrapper = OptionsAdapter.to_options_protocol(workflow_options)

        assert legacy_wrapper.publish is None
        assert legacy_wrapper.bump is None
        assert legacy_wrapper.all is None
        assert legacy_wrapper.resume_from is None
        assert legacy_wrapper.progress_file is None


class TestEdgeCasesAndDefaults:
    """Test edge cases and default value handling."""

    def test_empty_options_object(self) -> None:
        """Test handling of options object with no attributes."""

        # Create simple object without any attributes
        class EmptyOptions:
            pass

        empty_options = EmptyOptions()

        workflow_options = OptionsAdapter.from_options_protocol(empty_options)

        # All values should use defaults since getattr will fall back
        assert workflow_options.cleaning.clean is True  # Default
        assert workflow_options.testing.test is False  # Default
        assert workflow_options.execution.verbose is False  # Default

    def test_default_value_consistency(self) -> None:
        """Test that default values are consistent across conversions."""

        # Create options with minimal attributes
        class MinimalOptions:
            def __init__(self) -> None:
                self.clean = False
                self.verbose = True

        minimal_options = MinimalOptions()

        workflow_options = OptionsAdapter.from_options_protocol(minimal_options)

        # Verify explicit values are preserved
        assert workflow_options.cleaning.clean is False
        assert workflow_options.execution.verbose is True

        # Verify defaults are used for missing attributes
        assert workflow_options.cleaning.update_docs is False  # Default
        assert workflow_options.testing.benchmark is False  # Default
        assert workflow_options.hooks.skip_hooks is False  # Default

    def test_boolean_type_safety(self) -> None:
        """Test that boolean values are properly handled."""
        options = Mock(spec=OptionsProtocol)

        # Set various truthy/falsy values
        options.clean = 1  # Truthy
        options.test = 0  # Falsy
        options.verbose = ""  # Falsy
        options.interactive = "yes"  # Truthy

        workflow_options = OptionsAdapter.from_options_protocol(options)
        legacy_wrapper = OptionsAdapter.to_options_protocol(workflow_options)

        # Values should be preserved as-is (adapter doesn't convert types)
        assert legacy_wrapper.clean == 1
        assert legacy_wrapper.test == 0
        assert legacy_wrapper.verbose == ""
        assert legacy_wrapper.interactive == "yes"
