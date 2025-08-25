"""Tests for models.config module to complete coverage - FINAL LEBOWSKI PUSH!
Targeting 91% → 100% coverage (missing 9 backward compatibility properties).
"""

from crackerjack.models.config import (
    CleaningConfig,
    ExecutionConfig,
    GitConfig,
    HookConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
)


class TestWorkflowOptionsBackwardCompatibility:
    """Test backward compatibility properties in WorkflowOptions."""

    def test_clean_backward_compatibility_property(self) -> None:
        """Test the clean backward compatibility property."""
        cleaning_config = CleaningConfig(clean=True)
        options = WorkflowOptions(cleaning=cleaning_config)

        assert options.clean is True

    def test_test_backward_compatibility_property(self) -> None:
        """Test the test backward compatibility property."""
        testing_config = TestConfig(test=True)
        options = WorkflowOptions(testing=testing_config)

        assert options.test is True

    def test_skip_hooks_backward_compatibility_property(self) -> None:
        """Test the skip_hooks backward compatibility property."""
        hooks_config = HookConfig(skip_hooks=True)
        options = WorkflowOptions(hooks=hooks_config)

        assert options.skip_hooks is True

    def test_interactive_backward_compatibility_property(self) -> None:
        """Test the interactive backward compatibility property."""
        execution_config = ExecutionConfig(interactive=True)
        options = WorkflowOptions(execution=execution_config)

        assert options.interactive is True

    def test_verbose_backward_compatibility_property(self) -> None:
        """Test the verbose backward compatibility property."""
        execution_config = ExecutionConfig(verbose=True)
        options = WorkflowOptions(execution=execution_config)

        assert options.verbose is True

    def test_commit_backward_compatibility_property(self) -> None:
        """Test the commit backward compatibility property."""
        git_config = GitConfig(commit=True)
        options = WorkflowOptions(git=git_config)

        assert options.commit is True

    def test_publish_backward_compatibility_property(self) -> None:
        """Test the publish backward compatibility property."""
        publishing_config = PublishConfig(publish="patch")
        options = WorkflowOptions(publishing=publishing_config)

        assert options.publish == "patch"

    def test_bump_backward_compatibility_property(self) -> None:
        """Test the bump backward compatibility property."""
        publishing_config = PublishConfig(bump="minor")
        options = WorkflowOptions(publishing=publishing_config)

        assert options.bump == "minor"

    def test_no_config_updates_backward_compatibility_property(self) -> None:
        """Test the no_config_updates backward compatibility property."""
        execution_config = ExecutionConfig(no_config_updates=True)
        options = WorkflowOptions(execution=execution_config)

        assert options.no_config_updates is True

    def test_all_backward_compatibility_properties_together(self) -> None:
        """Test all backward compatibility properties work together."""
        options = WorkflowOptions(
            cleaning=CleaningConfig(clean=False),
            testing=TestConfig(test=False),
            hooks=HookConfig(skip_hooks=False),
            execution=ExecutionConfig(
                interactive=False,
                verbose=False,
                no_config_updates=False,
            ),
            git=GitConfig(commit=False),
            publishing=PublishConfig(publish=None, bump=None),
        )

        # Test all properties return expected values
        assert options.clean is False
        assert options.test is False
        assert options.skip_hooks is False
        assert options.interactive is False
        assert options.verbose is False
        assert options.commit is False
        assert options.publish is None
        assert options.bump is None
        assert options.no_config_updates is False
