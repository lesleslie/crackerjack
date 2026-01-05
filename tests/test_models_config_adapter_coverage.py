from unittest.mock import Mock

import pytest

from crackerjack.models.config import WorkflowOptions
from crackerjack.models.config_adapter import OptionsAdapter
from crackerjack.models.protocols import OptionsProtocol


class TestOptionsAdapter:
    @pytest.fixture
    def mock_options(self):
        options = Mock(spec=OptionsProtocol)

        options.clean = True
        options.update_docs = False
        options.force_update_docs = True
        options.compress_docs = False
        options.auto_compress_docs = True

        options.skip_hooks = False
        options.experimental_hooks = False
        options.enable_pyrefly = True
        options.enable_ty = False

        options.test = True
        options.benchmark = False
        options.benchmark_regression = True
        options.benchmark_regression_threshold = 0.2
        options.test_workers = 4
        options.test_timeout = 300

        options.publish = "patch"
        options.bump = "minor"
        options.all = "major"
        options.cleanup_pypi = True
        options.keep_releases = 5
        options.no_git_tags = False
        options.skip_version_check = True

        options.commit = True
        options.create_pr = False

        options.ai_agent = True
        options.autofix = True
        options.start_mcp_server = False

        options.interactive = False
        options.verbose = True
        options.async_mode = False
        options.no_config_updates = True

        options.track_progress = True
        options.resume_from = "session123"
        options.progress_file = "progress.json"

        return options

    @pytest.fixture
    def minimal_options(self):
        class MinimalOptions:
            def __init__(self) -> None:
                self.clean = False
                self.test = True
                self.verbose = False

        return MinimalOptions()

    def test_from_options_protocol_comprehensive(self, mock_options) -> None:
        workflow_options = OptionsAdapter.from_options_protocol(mock_options)

        assert workflow_options.cleaning.clean is True
        assert workflow_options.cleaning.update_docs is False
        assert workflow_options.cleaning.force_update_docs is True
        assert workflow_options.cleaning.compress_docs is False
        assert workflow_options.cleaning.auto_compress_docs is True

        assert workflow_options.hooks.skip_hooks is False
        assert workflow_options.hooks.experimental_hooks is False
        assert workflow_options.hooks.enable_pyrefly is True
        assert workflow_options.hooks.enable_ty is False

        assert workflow_options.testing.test is True
        assert workflow_options.testing.benchmark is False
        assert workflow_options.testing.benchmark_regression is True
        assert workflow_options.testing.benchmark_regression_threshold == 0.2
        assert workflow_options.testing.test_workers == 4
        assert workflow_options.testing.test_timeout == 300

        assert workflow_options.publishing.publish == "patch"
        assert workflow_options.publishing.bump == "minor"
        assert workflow_options.publishing.all == "major"
        assert workflow_options.publishing.cleanup_pypi is True
        assert workflow_options.publishing.keep_releases == 5
        assert workflow_options.publishing.no_git_tags is False
        assert workflow_options.publishing.skip_version_check is True

        assert workflow_options.git.commit is True
        assert workflow_options.git.create_pr is False

        assert workflow_options.ai.ai_agent is True
        assert workflow_options.ai.autofix is True
        assert workflow_options.ai.start_mcp_server is False

        assert workflow_options.execution.interactive is False
        assert workflow_options.execution.verbose is True
        assert workflow_options.execution.async_mode is False
        assert workflow_options.execution.no_config_updates is True

        assert workflow_options.progress.track_progress is True
        assert workflow_options.progress.resume_from == "session123"
        assert workflow_options.progress.progress_file == "progress.json"

    def test_from_options_protocol_with_defaults(self, minimal_options) -> None:
        workflow_options = OptionsAdapter.from_options_protocol(minimal_options)

        assert workflow_options.cleaning.clean is False
        assert workflow_options.cleaning.update_docs is False
        assert workflow_options.cleaning.force_update_docs is False
        assert workflow_options.cleaning.compress_docs is False
        assert workflow_options.cleaning.auto_compress_docs is False

        assert workflow_options.testing.test is True
        assert workflow_options.testing.benchmark is False
        assert workflow_options.testing.benchmark_regression is False
        assert workflow_options.testing.benchmark_regression_threshold == 0.1
        assert workflow_options.testing.test_workers == 0
        assert workflow_options.testing.test_timeout == 0

        assert workflow_options.execution.verbose is False
        assert workflow_options.execution.interactive is False
        assert workflow_options.execution.async_mode is False
        assert workflow_options.execution.no_config_updates is False

    def test_to_options_protocol(self) -> None:
        workflow_options = WorkflowOptions()

        result = OptionsAdapter.to_options_protocol(workflow_options)

        # After removing LegacyOptionsWrapper, to_options_protocol should return workflow_options directly
        assert result is workflow_options


class TestIntegrationBothDirections:
    def test_round_trip_conversion(self) -> None:
        original_options = Mock(spec=OptionsProtocol)
        original_options.clean = True
        original_options.test = False
        original_options.verbose = True
        original_options.commit = False
        original_options.ai_agent = True
        original_options.autofix = True
        original_options.interactive = False
        original_options.track_progress = True
        original_options.skip_hooks = False
        original_options.benchmark = True
        original_options.publish = "patch"
        original_options.update_docs = False
        original_options.cleanup_pypi = True

        workflow_options = OptionsAdapter.from_options_protocol(original_options)

        # After removing LegacyOptionsWrapper, to_options_protocol returns workflow_options directly
        result = OptionsAdapter.to_options_protocol(workflow_options)

        # Verify that the workflow_options has the expected values
        assert result.cleaning.clean == original_options.clean
        assert result.testing.test == original_options.test
        assert result.execution.verbose == original_options.verbose
        assert result.git.commit == original_options.commit
        assert result.ai.ai_agent == original_options.ai_agent
        assert result.ai.autofix == original_options.autofix
        assert result.execution.interactive == original_options.interactive
        assert result.progress.track_progress == original_options.track_progress
        assert result.hooks.skip_hooks == original_options.skip_hooks
        assert result.testing.benchmark == original_options.benchmark
        assert result.publishing.publish == original_options.publish
        assert result.cleaning.update_docs == original_options.update_docs
        assert result.publishing.cleanup_pypi == original_options.cleanup_pypi

    def test_complex_options_preservation(self) -> None:
        original_options = Mock(spec=OptionsProtocol)
        original_options.benchmark_regression_threshold = 0.15
        original_options.test_workers = 12
        original_options.test_timeout = 900
        original_options.keep_releases = 25
        original_options.resume_from = "complex_session_id_123"
        original_options.progress_file = "/ path / to / complex / progress.json"

        workflow_options = OptionsAdapter.from_options_protocol(original_options)
        result = OptionsAdapter.to_options_protocol(workflow_options)

        assert result.testing.benchmark_regression_threshold == 0.15
        assert result.testing.test_workers == 12
        assert result.testing.test_timeout == 900
        assert result.publishing.keep_releases == 25
        assert result.progress.resume_from == "complex_session_id_123"
        assert result.progress.progress_file == "/ path / to / complex / progress.json"

    def test_none_values_handling(self) -> None:
        original_options = Mock(spec=OptionsProtocol)
        original_options.publish = None
        original_options.bump = None
        original_options.all = None
        original_options.resume_from = None
        original_options.progress_file = None

        workflow_options = OptionsAdapter.from_options_protocol(original_options)
        result = OptionsAdapter.to_options_protocol(workflow_options)

        assert result.publishing.publish is None
        assert result.publishing.bump is None
        assert result.publishing.all is None
        assert result.progress.resume_from is None
        assert result.progress.progress_file is None


class TestEdgeCasesAndDefaults:
    def test_empty_options_object(self) -> None:
        class EmptyOptions:
            pass

        empty_options = EmptyOptions()

        workflow_options = OptionsAdapter.from_options_protocol(empty_options)

        assert workflow_options.cleaning.clean is True
        assert workflow_options.testing.test is False
        assert workflow_options.execution.verbose is False

    def test_default_value_consistency(self) -> None:
        class MinimalOptions:
            def __init__(self) -> None:
                self.clean = False
                self.verbose = True

        minimal_options = MinimalOptions()

        workflow_options = OptionsAdapter.from_options_protocol(minimal_options)

        assert workflow_options.cleaning.clean is False
        assert workflow_options.execution.verbose is True

        assert workflow_options.cleaning.update_docs is False
        assert workflow_options.testing.benchmark is False
        assert workflow_options.hooks.skip_hooks is False

    def test_boolean_type_safety(self) -> None:
        options = Mock(spec=OptionsProtocol)

        options.clean = 1
        options.test = 0
        options.verbose = ""
        options.interactive = "yes"

        workflow_options = OptionsAdapter.from_options_protocol(options)
        result = OptionsAdapter.to_options_protocol(workflow_options)

        assert result.cleaning.clean == 1
        assert result.testing.test == 0
        assert result.execution.verbose == ""
        assert result.execution.interactive == "yes"
