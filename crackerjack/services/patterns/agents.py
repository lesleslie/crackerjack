"""Agent count and configuration patterns."""

import re

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "agent_count_pattern": ValidatedPattern(
        name="agent_count_pattern",
        pattern=r"(\d+)\s+agents",
        replacement=r"\1 agents",
        test_cases=[
            ("9 agents", "9 agents"),
            ("12 agents", "12 agents"),
            ("5 agents", "5 agents"),
        ],
        description="Match agent count patterns for documentation consistency",
        flags=re.IGNORECASE,
    ),
    "specialized_agent_count_pattern": ValidatedPattern(
        name="specialized_agent_count_pattern",
        pattern=r"(\d+)\s+specialized\s+agents",
        replacement=r"\1 specialized agents",
        test_cases=[
            ("9 specialized agents", "9 specialized agents"),
            ("12 specialized agents", "12 specialized agents"),
            ("5 specialized agents", "5 specialized agents"),
        ],
        description="Match specialized agent count patterns for documentation "
        "consistency",
        flags=re.IGNORECASE,
    ),
    "total_agents_config_pattern": ValidatedPattern(
        name="total_agents_config_pattern",
        pattern=r'total_agents["\'][\s]*: \s*(\d+)',
        replacement=r'total_agents": \1',
        test_cases=[
            ('total_agents": 9', 'total_agents": 9'),
            ("total_agents': 12", 'total_agents": 12'),
            ('total_agents" : 5', 'total_agents": 5'),
        ],
        description="Match total agents configuration patterns",
        flags=re.IGNORECASE,
    ),
    "sub_agent_count_pattern": ValidatedPattern(
        name="sub_agent_count_pattern",
        pattern=r"(\d+)\s+sub-agents",
        replacement=r"\1 sub-agents",
        test_cases=[
            ("9 sub-agents", "9 sub-agents"),
            ("12 sub-agents", "12 sub-agents"),
            ("5 sub-agents", "5 sub-agents"),
        ],
        description="Match sub-agent count patterns for documentation consistency",
        flags=re.IGNORECASE,
    ),
    "update_agent_count": ValidatedPattern(
        name="update_agent_count",
        pattern=r"\b(\d+)\s+agents\b",
        replacement=r"NEW_COUNT agents",
        test_cases=[
            ("9 agents working", "NEW_COUNT agents working"),
            ("We have 12 agents ready", "We have NEW_COUNT agents ready"),
            ("All 5 agents are active", "All NEW_COUNT agents are active"),
        ],
        description="Update agent count references (NEW_COUNT replaced dynamically)",
    ),
    "update_specialized_agent_count": ValidatedPattern(
        name="update_specialized_agent_count",
        pattern=r"\b(\d+)\s+specialized\s+agents\b",
        replacement=r"NEW_COUNT specialized agents",
        test_cases=[
            (
                "9 specialized agents available",
                "NEW_COUNT specialized agents available",
            ),
            ("We have 12 specialized agents", "We have NEW_COUNT specialized agents"),
            ("All 5 specialized agents work", "All NEW_COUNT specialized agents work"),
        ],
        description="Update specialized agent count references (NEW_COUNT replaced"
        " dynamically)",
    ),
    "update_total_agents_config": ValidatedPattern(
        name="update_total_agents_config",
        pattern=r'total_agents["\'][\s]*: \s*\d+',
        replacement=r'total_agents": NEW_COUNT',
        test_cases=[
            ('total_agents": 9', 'total_agents": NEW_COUNT'),
            ("total_agents': 12", 'total_agents": NEW_COUNT'),
            ('total_agents" : 5', 'total_agents": NEW_COUNT'),
        ],
        description="Update total agents configuration (NEW_COUNT replaced"
        " dynamically)",
    ),
    "update_sub_agent_count": ValidatedPattern(
        name="update_sub_agent_count",
        pattern=r"\b(\d+)\s+sub-agents\b",
        replacement=r"NEW_COUNT sub-agents",
        test_cases=[
            ("9 sub-agents working", "NEW_COUNT sub-agents working"),
            ("We have 12 sub-agents ready", "We have NEW_COUNT sub-agents ready"),
            ("All 5 sub-agents are active", "All NEW_COUNT sub-agents are active"),
        ],
        description="Update sub-agent count references (NEW_COUNT replaced"
        " dynamically)",
    ),
}
