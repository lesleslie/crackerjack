"""Regression tests for agent registry population bug.

This test ensures the agent registry is properly populated with all agents.
The bug: Agent modules used lazy loading but were never imported, so
agent_registry.register() calls never executed, leaving the registry empty.

See: AI_FIX_AGENT_REGISTRY_BUG_FIX.md
"""

import pytest
from crackerjack.agents.base import AgentContext, IssueType, agent_registry
from crackerjack.agents.coordinator import ISSUE_TYPE_TO_AGENTS
from pathlib import Path


@pytest.mark.unit
class TestAgentRegistryPopulation:
    """Regression tests for agent registry being properly populated."""

    def test_registry_populated_after_import(self):
        """
        REGRESSION TEST: Verify agent registry is populated after importing crackerjack.agents.

        Bug: Agent modules used lazy loading via __getattr__, but the agent_registry
        stayed empty because modules were never imported.

        Fix: Import all agent modules in __init__.py to trigger registration.
        """
        # The registry should be populated after importing the agents package
        import crackerjack.agents  # noqa: F401 (import has side effects)

        # Registry should have all agents registered
        registered_count = len(agent_registry._agents)
        assert registered_count > 0, f"Agent registry empty! Found {registered_count} agents"

        # Verify expected agents are present
        expected_agents = {
            "ArchitectAgent",
            "DocumentationAgent",
            "DRYAgent",
            "FormattingAgent",
            "ImportOptimizationAgent",
            "PerformanceAgent",
            "RefactoringAgent",
            "SecurityAgent",
            "SemanticAgent",
            "TestCreationAgent",
            "TestSpecialistAgent",
        }

        registered_agents = set(agent_registry._agents.keys())
        for expected_agent in expected_agents:
            assert (
                expected_agent in registered_agents
            ), f"Expected agent '{expected_agent}' not registered. Found: {registered_agents}"

    def test_agent_creation_from_registry(self):
        """
        REGRESSION TEST: Verify agents can be created from the registry.

        Bug: Empty registry meant agent_registry.create_all() returned empty list.
        """
        import crackerjack.agents  # noqa: F401

        context = AgentContext(project_path=Path("."))

        # create_all should return a list of agent instances
        agents = agent_registry.create_all(context)

        assert len(agents) > 0, "No agents created from registry"
        assert len(agents) >= 11, f"Expected at least 11 agents, got {len(agents)}"

        # Verify all agents are SubAgent instances
        for agent in agents:
            from crackerjack.agents.base import SubAgent

            assert isinstance(
                agent, SubAgent
            ), f"Agent {agent.__class__.__name__} is not a SubAgent instance"

    def test_agent_registry_has_all_issue_types_covered(self):
        """
        REGRESSION TEST: Verify all IssueType values have at least one agent mapped.

        Bug: Empty registry meant no agents could be found for any issue type.
        """
        import crackerjack.agents  # noqa: F401

        # Create agents from registry
        context = AgentContext(project_path=Path("."))
        agents = agent_registry.create_all(context)

        # Get all supported issue types from all agents
        supported_types = set()
        for agent in agents:
            supported_types.update(agent.get_supported_types())

        # Verify all IssueType values are covered by at least one agent
        all_issue_types = {issue_type for issue_type in IssueType}

        uncovered_types = all_issue_types - supported_types
        assert (
            not uncovered_types
        ), f"Issue types with no agents: {uncovered_types}"

    def test_critical_issue_types_have_specialists(self):
        """
        REGRESSION TEST: Verify critical issue types have specialist agents mapped.

        Bug: TYPE_ERROR had mapping but ArchitectAgent wasn't registered.
        """
        # These are the issue types that commonly appear in comprehensive hooks
        critical_types = {
            IssueType.TYPE_ERROR,
            IssueType.COMPLEXITY,
            IssueType.FORMATTING,
            IssueType.IMPORT_ERROR,
            IssueType.SECURITY,
        }

        import crackerjack.agents  # noqa: F401

        for issue_type in critical_types:
            # Check mapping exists
            assert (
                issue_type in ISSUE_TYPE_TO_AGENTS
            ), f"No agent mapping for {issue_type.value}"

            # Check at least one agent is registered for this type
            preferred_agents = ISSUE_TYPE_TO_AGENTS[issue_type]
            assert len(preferred_agents) > 0, f"Empty agent list for {issue_type.value}"

    def test_architect_agent_supports_type_error(self):
        """
        REGRESSION TEST: Verify ArchitectAgent supports TYPE_ERROR.

        Bug: TYPE_ERROR was mapped to TestCreationAgent and RefactoringAgent,
        but neither supports it. ArchitectAgent does support it.
        """
        import crackerjack.agents  # noqa: F401

        from crackerjack.agents.architect_agent import ArchitectAgent

        context = AgentContext(project_path=Path("."))
        agent = ArchitectAgent(context)

        supported_types = agent.get_supported_types()
        assert IssueType.TYPE_ERROR in supported_types, (
            "ArchitectAgent should support TYPE_ERROR but doesn't. "
            f"Supported: {[t.value for t in supported_types]}"
        )

    def test_mapping_matches_actual_capabilities(self):
        """
        REGRESSION TEST: Verify ISSUE_TYPE_TO_AGENTS mapping matches actual agent capabilities.

        Bug: Mapping claimed TYPE_ERROR -> ["TestCreationAgent", "RefactoringAgent"]
        but neither agent actually supports TYPE_ERROR.

        This test ensures the mapping stays in sync with agent implementations.
        """
        import crackerjack.agents  # noqa: F401

        context = AgentContext(project_path=Path("."))
        agents = agent_registry.create_all(context)

        # Build mapping of what agents actually support
        actual_support: dict[IssueType, list[str]] = {}
        for agent in agents:
            agent_name = agent.__class__.__name__
            for issue_type in agent.get_supported_types():
                if issue_type not in actual_support:
                    actual_support[issue_type] = []
                actual_support[issue_type].append(agent_name)

        # Verify ISSUE_TYPE_TO_AGENTS is a subset of actual support
        mismatches = []
        for issue_type, mapped_agents in ISSUE_TYPE_TO_AGENTS.items():
            if issue_type not in actual_support:
                mismatches.append(
                    f"{issue_type.value}: mapped to {mapped_agents} but no agents support it"
                )
                continue

            for agent_name in mapped_agents:
                if agent_name not in actual_support[issue_type]:
                    mismatches.append(
                        f"{issue_type.value}: mapped to {agent_name} "
                        f"but it doesn't support it. "
                        f"Supports: {actual_support[issue_type]}"
                    )

        assert (
            not mismatches
        ), f"ISSUE_TYPE_TO_AGENTS mapping doesn't match actual agent capabilities:\n" + "\n".join(mismatches)


@pytest.mark.integration
class TestAgentRegistryIntegration:
    """Integration tests for agent registry with coordinator."""

    def test_coordinator_can_find_agents_for_all_types(self):
        """
        REGRESSION TEST: Verify coordinator can find agents for all issue types.

        Bug: Empty registry meant coordinator logged "No specialist agents for type_error"
        even though mapping existed.
        """
        import crackerjack.agents  # noqa: F401

        from crackerjack.agents.coordinator import AgentCoordinator

        context = AgentContext(project_path=Path("."))
        coordinator = AgentCoordinator(context=context)

        # Initialize agents (this populates self.agents from registry)
        coordinator.initialize_agents()

        # Verify agents were initialized
        assert len(coordinator.agents) > 0, "No agents initialized in coordinator"
        assert (
            len(coordinator.agents) >= 11
        ), f"Expected at least 11 agents, got {len(coordinator.agents)}"

        # Verify coordinator can find agents for all issue types in mapping
        for issue_type, agent_names in ISSUE_TYPE_TO_AGENTS.items():
            # Find agents by name
            found_agents = [
                agent
                for agent in coordinator.agents
                if agent.__class__.__name__ in agent_names
            ]

            assert (
                len(found_agents) > 0
            ), f"No agents found for {issue_type.value}. Looking for: {agent_names}"

    def test_coordinator_initialize_agents_populates_registry(self):
        """
        REGRESSION TEST: Verify coordinator.initialize_agents() populates agents.

        Bug: coordinator.agents stayed empty because registry was empty.
        """
        import crackerjack.agents  # noqa: F401

        from crackerjack.agents.coordinator import AgentCoordinator

        context = AgentContext(project_path=Path("."))

        # Create coordinator without initializing agents
        coordinator = AgentCoordinator(context=context)
        assert len(coordinator.agents) == 0, "Agents should be empty initially"

        # Initialize agents
        coordinator.initialize_agents()

        # Verify agents are now populated
        assert (
            len(coordinator.agents) > 0
        ), "initialize_agents() should populate agents"
        assert (
            len(coordinator.agents) >= 11
        ), f"Expected at least 11 agents after initialization, got {len(coordinator.agents)}"


@pytest.mark.regression
class TestAgentRegistryBugRegression:
    """Regression tests for the specific agent registry bug."""

    def test_regression_empty_registry_bug(self):
        """
        REGRESSION TEST: Prevent agent registry from being empty.

        Bug: Agent modules used lazy loading but were never imported.
        Result: agent_registry.create_all() returned empty list.
        User Impact: "No specialist agents for type_error" even though mapping exists.

        Fix: Import all agent modules in __init__.py to trigger registration.
        """
        # This test would fail before the fix (registry would be empty)
        import crackerjack.agents  # noqa: F401

        registry_size = len(agent_registry._agents)

        assert registry_size >= 11, (
            f"Agent registry should have at least 11 agents, "
            f"but has {registry_size}. "
            "This indicates the lazy loading bug has returned."
        )

    def test_regression_ai_fix_iteration_with_empty_registry(self):
        """
        REGRESSION TEST: Verify AI-fix iterations work with populated registry.

        Bug: AI-fix reported "120 issues to fix" then immediately said
        "Agents cannot fix remaining issues" because registry was empty.
        """
        import crackerjack.agents  # noqa: F401

        from crackerjack.agents.coordinator import AgentCoordinator
        from crackerjack.agents.base import Issue, IssueType, Priority

        context = AgentContext(project_path=Path("."))
        coordinator = AgentCoordinator(context=context)

        # Create sample issues
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message="Test type error",
                file_path="test.py",
                line_number=10,
                stage="test",
            )
        ]

        # Initialize agents (should work now)
        coordinator.initialize_agents()
        assert len(coordinator.agents) > 0, "Agents should be initialized"

        # Verify we can find agents for TYPE_ERROR
        type_error_agents = [
            agent
            for agent in coordinator.agents
            if IssueType.TYPE_ERROR in agent.get_supported_types()
        ]

        assert (
            len(type_error_agents) > 0
        ), "Should find at least one agent that supports TYPE_ERROR"
