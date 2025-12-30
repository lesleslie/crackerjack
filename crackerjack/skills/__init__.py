"""
Crackerjack Skills System

This module provides a multi-layered skill architecture that bridges
Crackerjack's AI agents with MCP tool capabilities.

Three Implementation Approaches:
1. Agent Capabilities → Skills (internal agent capabilities mapped to skills)
2. MCP Tools → Skills (existing tools grouped into purpose-based skills)
3. Hybrid Agent Skills (agent-based skills with tool delegation)

Usage:
    from crackerjack.skills import (
        AgentSkillRegistry,
        MCPSkillRegistry,
        HybridSkillRegistry,
        register_all_skills,
    )

    # Register all skills with MCP app
    register_all_skills(mcp_app, context)
"""

from .agent_skills import AgentSkill, AgentSkillRegistry
from .hybrid_skills import HybridSkill, HybridSkillRegistry
from .mcp_skills import MCPSkill, MCPSkillRegistry
from .registration import register_all_skills

__all__ = [
    "AgentSkill",
    "AgentSkillRegistry",
    "MCPSkill",
    "MCPSkillRegistry",
    "HybridSkill",
    "HybridSkillRegistry",
    "register_all_skills",
]
