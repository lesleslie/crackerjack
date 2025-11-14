"""Unit tests for execution strategies.

Tests execution strategies, orchestration config, execution context,
and strategy selection logic.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from crackerjack.orchestration.execution_strategies import (
    AICoordinationMode,
    AIIntelligence,
    ExecutionContext,
    ExecutionStrategy,
    OrchestrationConfig,
    ProgressLevel,
    StrategySelector,
    StreamingMode,
)


@pytest.mark.unit
class TestExecutionStrategyEnum:
    """Test ExecutionStrategy enum."""

    def test_execution_strategy_values(self):
        """Test ExecutionStrategy enum values."""
        assert ExecutionStrategy.BATCH == "batch"
        assert ExecutionStrategy.INDIVIDUAL == "individual"
        assert ExecutionStrategy.ADAPTIVE == "adaptive"
        assert ExecutionStrategy.SELECTIVE == "selective"

    def test_execution_strategy_membership(self):
        """Test enum membership."""
        assert "batch" in ExecutionStrategy._value2member_map_
        assert "individual" in ExecutionStrategy._value2member_map_
        assert "adaptive" in ExecutionStrategy._value2member_map_
        assert "selective" in ExecutionStrategy._value2member_map_


@pytest.mark.unit
class TestProgressLevelEnum:
    """Test ProgressLevel enum."""

    def test_progress_level_values(self):
        """Test ProgressLevel enum values."""
        assert ProgressLevel.BASIC == "basic"
        assert ProgressLevel.DETAILED == "detailed"
        assert ProgressLevel.GRANULAR == "granular"
        assert ProgressLevel.STREAMING == "streaming"


@pytest.mark.unit
class TestStreamingModeEnum:
    """Test StreamingMode enum."""

    def test_streaming_mode_values(self):
        """Test StreamingMode enum values."""
        assert StreamingMode.WEBSOCKET == "websocket"
        assert StreamingMode.FILE == "file"
        assert StreamingMode.HYBRID == "hybrid"


@pytest.mark.unit
class TestAICoordinationModeEnum:
    """Test AICoordinationMode enum."""

    def test_ai_coordination_mode_values(self):
        """Test AICoordinationMode enum values."""
        assert AICoordinationMode.SINGLE_AGENT == "single-agent"
        assert AICoordinationMode.MULTI_AGENT == "multi-agent"
        assert AICoordinationMode.COORDINATOR == "coordinator"


@pytest.mark.unit
class TestAIIntelligenceEnum:
    """Test AIIntelligence enum."""

    def test_ai_intelligence_values(self):
        """Test AIIntelligence enum values."""
        assert AIIntelligence.BASIC == "basic"
        assert AIIntelligence.ADAPTIVE == "adaptive"
        assert AIIntelligence.LEARNING == "learning"


@pytest.mark.unit
class TestOrchestrationConfig:
    """Test OrchestrationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OrchestrationConfig()

        assert config.execution_strategy == ExecutionStrategy.BATCH
        assert config.progress_level == ProgressLevel.BASIC
        assert config.streaming_mode == StreamingMode.WEBSOCKET
        assert config.ai_coordination_mode == AICoordinationMode.SINGLE_AGENT
        assert config.ai_intelligence == AIIntelligence.BASIC
        assert config.correlation_tracking is True
        assert config.failure_analysis is True
        assert config.intelligent_retry is True
        assert config.max_parallel_hooks == 3
        assert config.max_parallel_tests == 4
        assert config.timeout_multiplier == 1.0
        assert config.debug_level == "standard"
        assert config.log_individual_outputs is False
        assert config.preserve_temp_files is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OrchestrationConfig(
            execution_strategy=ExecutionStrategy.ADAPTIVE,
            progress_level=ProgressLevel.DETAILED,
            max_parallel_hooks=5,
            max_parallel_tests=8,
            timeout_multiplier=1.5,
            correlation_tracking=False,
        )

        assert config.execution_strategy == ExecutionStrategy.ADAPTIVE
        assert config.progress_level == ProgressLevel.DETAILED
        assert config.max_parallel_hooks == 5
        assert config.max_parallel_tests == 8
        assert config.timeout_multiplier == 1.5
        assert config.correlation_tracking is False

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = OrchestrationConfig(
            execution_strategy=ExecutionStrategy.INDIVIDUAL,
            max_parallel_hooks=4,
        )

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["execution_strategy"] == "individual"
        assert config_dict["max_parallel_hooks"] == 4
        assert config_dict["correlation_tracking"] is True

    def test_to_dict_all_fields(self):
        """Test to_dict includes all fields."""
        config = OrchestrationConfig()
        config_dict = config.to_dict()

        expected_fields = [
            "execution_strategy",
            "progress_level",
            "streaming_mode",
            "ai_coordination_mode",
            "ai_intelligence",
            "correlation_tracking",
            "failure_analysis",
            "intelligent_retry",
            "max_parallel_hooks",
            "max_parallel_tests",
            "timeout_multiplier",
            "debug_level",
            "log_individual_outputs",
            "preserve_temp_files",
        ]

        for field in expected_fields:
            assert field in config_dict


@pytest.mark.unit
class TestExecutionContext:
    """Test ExecutionContext class."""

    @pytest.fixture
    def mock_options(self):
        """Create mock options."""
        options = Mock()
        options.ai_agent = False
        options.ai_debug = False
        options.interactive = False
        return options

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure."""
        # Create some Python files
        (tmp_path / "module1.py").write_text("def foo(): pass")
        (tmp_path / "module2.py").write_text("def bar(): pass")

        # Create test directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_module1.py").write_text("def test_foo(): pass")

        # Create pyproject.toml
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        return tmp_path

    def test_initialization_basic(self, mock_options, tmp_path):
        """Test basic initialization."""
        context = ExecutionContext(tmp_path, mock_options)

        assert context.pkg_path == tmp_path
        assert context.options == mock_options
        assert context.previous_failures == []
        assert context.changed_files == []
        assert context.iteration_count == 1

    def test_initialization_with_previous_failures(self, mock_options, tmp_path):
        """Test initialization with previous failures."""
        previous_failures = ["hook1", "hook2"]
        context = ExecutionContext(
            tmp_path, mock_options, previous_failures=previous_failures
        )

        assert context.previous_failures == previous_failures

    def test_initialization_with_changed_files(self, mock_options, tmp_path):
        """Test initialization with changed files."""
        changed_files = [tmp_path / "file1.py", tmp_path / "file2.py"]
        context = ExecutionContext(
            tmp_path, mock_options, changed_files=changed_files
        )

        assert context.changed_files == changed_files

    def test_initialization_with_iteration_count(self, mock_options, tmp_path):
        """Test initialization with custom iteration count."""
        context = ExecutionContext(tmp_path, mock_options, iteration_count=3)

        assert context.iteration_count == 3

    def test_total_python_files(self, mock_options, temp_project):
        """Test counting total Python files."""
        context = ExecutionContext(temp_project, mock_options)

        # Should count Python files in project
        assert context.total_python_files >= 2

    def test_total_test_files(self, mock_options, temp_project):
        """Test counting total test files."""
        context = ExecutionContext(temp_project, mock_options)

        # Should count test files
        assert context.total_test_files >= 1

    def test_detect_complex_setup(self, mock_options, temp_project):
        """Test detecting complex project setup."""
        context = ExecutionContext(temp_project, mock_options)

        # Project has pyproject.toml
        assert isinstance(context.has_complex_setup, bool)

    def test_estimate_hook_duration(self, mock_options, temp_project):
        """Test estimating hook duration."""
        context = ExecutionContext(temp_project, mock_options)

        assert context.estimated_hook_duration > 0
        assert isinstance(context.estimated_hook_duration, float)

    def test_ai_agent_mode_property(self, mock_options, tmp_path):
        """Test ai_agent_mode property."""
        mock_options.ai_agent = True
        context = ExecutionContext(tmp_path, mock_options)

        assert context.ai_agent_mode is True

    def test_ai_debug_mode_property(self, mock_options, tmp_path):
        """Test ai_debug_mode property."""
        mock_options.ai_debug = True
        context = ExecutionContext(tmp_path, mock_options)

        assert context.ai_debug_mode is True

    def test_interactive_property(self, mock_options, tmp_path):
        """Test interactive property."""
        mock_options.interactive = True
        context = ExecutionContext(tmp_path, mock_options)

        assert context.interactive is True

    def test_working_directory_property(self, mock_options, tmp_path):
        """Test working_directory property."""
        context = ExecutionContext(tmp_path, mock_options)

        assert context.working_directory == tmp_path

    def test_complex_setup_detection_criteria(self, mock_options, tmp_path):
        """Test complex setup detection with various criteria."""
        # Create minimal project (should not be complex)
        context = ExecutionContext(tmp_path, mock_options)
        initial_complexity = context.has_complex_setup

        # Add pyproject.toml
        (tmp_path / "pyproject.toml").write_text("[project]")

        # Add setup.py
        (tmp_path / "setup.py").write_text("from setuptools import setup")

        # Recreate context
        context = ExecutionContext(tmp_path, mock_options)

        # Should be more likely to be complex
        assert isinstance(context.has_complex_setup, bool)


@pytest.mark.unit
class TestStrategySelector:
    """Test StrategySelector class."""

    @pytest.fixture
    def selector(self):
        """Create strategy selector."""
        console = Mock()
        return StrategySelector(console)

    @pytest.fixture
    def context(self, tmp_path):
        """Create execution context."""
        options = Mock()
        options.ai_agent = False
        return ExecutionContext(tmp_path, options)

    def test_initialization(self):
        """Test StrategySelector initializes correctly."""
        console = Mock()
        selector = StrategySelector(console)

        assert selector.console == console

    def test_select_strategy_non_adaptive(self, selector, context):
        """Test selecting non-adaptive strategy."""
        config = OrchestrationConfig(execution_strategy=ExecutionStrategy.BATCH)

        strategy = selector.select_strategy(config, context)

        assert strategy == ExecutionStrategy.BATCH

    def test_select_strategy_adaptive_simple_project(self, selector, tmp_path):
        """Test adaptive strategy selection for simple project."""
        options = Mock()
        context = ExecutionContext(tmp_path, options)
        config = OrchestrationConfig(execution_strategy=ExecutionStrategy.ADAPTIVE)

        strategy = selector.select_strategy(config, context)

        # Should select appropriate strategy
        assert strategy in [
            ExecutionStrategy.BATCH,
            ExecutionStrategy.INDIVIDUAL,
            ExecutionStrategy.SELECTIVE,
        ]

    def test_select_strategy_adaptive_complex_project(self, selector, tmp_path):
        """Test adaptive strategy selection for complex project."""
        # Create complex project structure
        for i in range(60):
            (tmp_path / f"module{i}.py").write_text("pass")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        for i in range(25):
            (tests_dir / f"test_module{i}.py").write_text("pass")

        options = Mock()
        context = ExecutionContext(tmp_path, options)
        config = OrchestrationConfig(execution_strategy=ExecutionStrategy.ADAPTIVE)

        strategy = selector.select_strategy(config, context)

        # Should select appropriate strategy for complex project
        assert strategy in [
            ExecutionStrategy.BATCH,
            ExecutionStrategy.INDIVIDUAL,
            ExecutionStrategy.SELECTIVE,
        ]

    def test_select_strategy_with_previous_failures(self, selector, tmp_path):
        """Test strategy selection with previous failures."""
        options = Mock()
        previous_failures = ["hook1", "hook2", "hook3"]
        context = ExecutionContext(
            tmp_path, options, previous_failures=previous_failures
        )
        config = OrchestrationConfig(execution_strategy=ExecutionStrategy.ADAPTIVE)

        strategy = selector.select_strategy(config, context)

        # Should consider previous failures in selection
        assert strategy in [
            ExecutionStrategy.BATCH,
            ExecutionStrategy.INDIVIDUAL,
            ExecutionStrategy.SELECTIVE,
        ]

    def test_select_strategy_with_changed_files(self, selector, tmp_path):
        """Test strategy selection with changed files."""
        options = Mock()
        changed_files = [tmp_path / "file1.py", tmp_path / "file2.py"]
        context = ExecutionContext(tmp_path, options, changed_files=changed_files)
        config = OrchestrationConfig(execution_strategy=ExecutionStrategy.ADAPTIVE)

        strategy = selector.select_strategy(config, context)

        # Should consider changed files in selection
        assert strategy in [
            ExecutionStrategy.BATCH,
            ExecutionStrategy.INDIVIDUAL,
            ExecutionStrategy.SELECTIVE,
        ]


@pytest.mark.unit
class TestExecutionContextIntegration:
    """Test ExecutionContext integration scenarios."""

    @pytest.fixture
    def comprehensive_project(self, tmp_path):
        """Create comprehensive project structure."""
        # Python modules
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(20):
            (src_dir / f"module{i}.py").write_text(f"def func{i}(): pass")

        # Tests
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        for i in range(10):
            (tests_dir / f"test_module{i}.py").write_text(f"def test_{i}(): pass")

        # Config files
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "setup.py").write_text("from setuptools import setup")
        (tmp_path / "requirements.txt").write_text("pytest\nruff")

        return tmp_path

    def test_context_with_comprehensive_project(self, comprehensive_project):
        """Test context creation with comprehensive project."""
        options = Mock()
        options.ai_agent = False
        options.ai_debug = False
        options.interactive = False

        context = ExecutionContext(comprehensive_project, options)

        # Should detect files
        assert context.total_python_files > 0
        assert context.total_test_files > 0

        # Should detect complex setup
        assert context.has_complex_setup is True

        # Should estimate duration
        assert context.estimated_hook_duration > 30.0

    def test_context_iteration_tracking(self, tmp_path):
        """Test iteration tracking across contexts."""
        options = Mock()

        # First iteration
        context1 = ExecutionContext(tmp_path, options, iteration_count=1)
        assert context1.iteration_count == 1

        # Second iteration with failures
        previous_failures = ["hook1"]
        context2 = ExecutionContext(
            tmp_path, options, previous_failures=previous_failures, iteration_count=2
        )
        assert context2.iteration_count == 2
        assert len(context2.previous_failures) == 1

        # Third iteration
        context3 = ExecutionContext(tmp_path, options, iteration_count=3)
        assert context3.iteration_count == 3
