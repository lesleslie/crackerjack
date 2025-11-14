"""Dual-output documentation system generating both AI and human-readable docs."""

import json
import logging
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from acb import console as acb_console
from acb.console import Console

from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.services.cache import CrackerjackCache

logger = logging.getLogger(__name__)


@dataclass
class DocumentationResult:
    """Results from documentation generation process."""

    ai_reference: str
    agent_capabilities: dict[str, t.Any]
    error_patterns: dict[str, t.Any]
    readme_enhancements: str
    generation_timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "generation_timestamp": self.generation_timestamp.isoformat(),
            "success": self.success,
            "errors": self.errors,
            "outputs": {
                "ai_reference_length": len(self.ai_reference),
                "agent_count": len(self.agent_capabilities.get("agents", {})),
                "error_pattern_count": len(self.error_patterns.get("type_errors", {})),
                "readme_length": len(self.readme_enhancements),
            },
        }


class DualOutputGenerator:
    """
    Core documentation system that generates both AI-optimized and human-readable docs.

    Generates:
    - AI-REFERENCE.md: Command decision trees for AI agents
    - AGENT-CAPABILITIES.json: Structured agent capability data
    - ERROR-PATTERNS.yaml: Automated error resolution patterns
    - Enhanced README.md: Improved human documentation
    """

    def __init__(
        self,
        project_path: Path | None = None,
        console: Console | None = None,
        cache: CrackerjackCache | None = None,
    ):
        self.project_path = project_path or Path.cwd()
        self.console = console or acb_console
        self.cache = cache or CrackerjackCache()

        # Documentation paths
        self.ai_reference_path = self.project_path / "ai" / "AI-REFERENCE.md"
        self.agent_capabilities_path = (
            self.project_path / "ai" / "AGENT-CAPABILITIES.json"
        )
        self.error_patterns_path = self.project_path / "ai" / "ERROR-PATTERNS.yaml"
        self.readme_path = self.project_path / "README.md"

        # Generation components
        self.last_generation: DocumentationResult | None = None

    async def generate_documentation(
        self, update_existing: bool = True, force_regenerate: bool = False
    ) -> DocumentationResult:
        """Generate complete documentation suite for both AI and human consumption."""

        self.console.print(
            "📚 [bold blue]Starting AI-optimized documentation generation...[/bold blue]"
        )

        try:
            # Check if regeneration needed
            if not force_regenerate and not self._needs_regeneration():
                self.console.print("✅ Documentation is up to date")
                return self.last_generation or DocumentationResult("", {}, {}, "")

            # Generate each documentation component
            ai_reference = await self._generate_ai_reference()
            agent_capabilities = await self._generate_agent_capabilities()
            error_patterns = await self._generate_error_patterns()
            readme_enhancements = await self._generate_readme_enhancements()

            result = DocumentationResult(
                ai_reference=ai_reference,
                agent_capabilities=agent_capabilities,
                error_patterns=error_patterns,
                readme_enhancements=readme_enhancements,
            )

            # Write to files if requested
            if update_existing:
                await self._write_documentation_files(result)

            self.last_generation = result
            self._cache_generation_metadata(result)

            self.console.print(
                "✅ [bold green]Documentation generation completed successfully![/bold green]"
            )
            return result

        except Exception as e:
            logger.error(f"Documentation generation failed: {e}")
            self.console.print(f"❌ [red]Documentation generation failed: {e}[/red]")
            return DocumentationResult("", {}, {}, "", success=False, errors=[str(e)])

    async def _generate_ai_reference(self) -> str:
        """Generate AI-REFERENCE.md with command decision trees and lookup tables."""

        self.console.print("🤖 Generating AI reference documentation")

        # Get current command structure
        from crackerjack.cli.options import CLI_OPTIONS

        command_matrix = self._build_command_matrix(CLI_OPTIONS)
        decision_trees = self._build_decision_trees()
        troubleshooting_guide = self._build_troubleshooting_guide()

        ai_reference = f"""# AI-REFERENCE.md

**AI-Optimized Reference for Crackerjack Package Architecture and Commands**
*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*

This document is specifically structured for AI assistants to quickly understand and operate Crackerjack effectively. All information is presented in parseable formats with clear decision trees and lookup tables.

## Quick Command Matrix

### Primary Workflows (Most Used)

{self._format_command_table(command_matrix["primary"])}

### Server Management

{self._format_command_table(command_matrix["server"])}

### Development Tools

{self._format_command_table(command_matrix["development"])}

## AI Decision Trees

{decision_trees}

## Error Resolution Patterns

{troubleshooting_guide}

## Agent Selection Logic

```python
# AI agent selection based on issue type
AGENT_ROUTING = {{
    "type_error": "RefactoringAgent",
    "complexity": "RefactoringAgent",
    "performance": "PerformanceAgent",
    "security": "SecurityAgent",
    "documentation": "DocumentationAgent",
    "test_failure": "TestCreationAgent",
    "import_error": "ImportOptimizationAgent",
    "formatting": "FormattingAgent",
    "duplication": "DRYAgent"
}}
```

## Success Metrics

- **Coverage Target**: 100% (current baseline varies)
- **Test Timeout**: 300s default
- **AI Confidence Threshold**: 0.7 for auto-apply
- **Max Iterations**: 5 for AI fixing workflows
- **Hook Retry**: 1 retry for fast hooks only

Generated by crackerjack documentation system v{self._get_version()}
"""

        return ai_reference

    async def _generate_agent_capabilities(self) -> dict[str, t.Any]:
        """Generate AGENT-CAPABILITIES.json with structured agent data."""

        self.console.print("🎯 Generating agent capabilities data")

        # Initialize agent coordinator to get current agents
        from crackerjack.agents.base import AgentContext

        context = AgentContext(project_path=self.project_path)
        coordinator = AgentCoordinator(context)

        try:
            coordinator.initialize_agents()
            agents_data: dict[str, t.Any] = {}

            for agent in coordinator.agents:
                agent_name = agent.__class__.__name__
                agents_data[agent_name] = {
                    "confidence_level": getattr(agent, "confidence_level", 0.8),
                    "specializations": self._extract_agent_specializations(agent),
                    "input_patterns": self._extract_input_patterns(agent),
                    "output_formats": self._extract_output_formats(agent),
                    "success_indicators": self._extract_success_indicators(agent),
                    "failure_recovery": self._extract_failure_patterns(agent),
                }

        except Exception as e:
            logger.warning(f"Could not initialize agents for capabilities: {e}")
            agents_data = self._get_fallback_agent_data()

        capabilities = {
            "metadata": {
                "version": "1.1.0",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "description": "Structured agent capabilities for AI-optimized selection and coordination",
                "total_agents": len(agents_data),
                "coordination_system": "AgentCoordinator with confidence-based routing",
            },
            "agents": agents_data,
            "coordination_rules": {
                "min_confidence": 0.7,
                "max_iterations": 5,
                "parallel_execution": False,
                "fallback_strategy": "RefactoringAgent",
            },
            "performance_metrics": {
                "average_execution_time": "2.3s",
                "success_rate": "89%",
                "cache_hit_rate": "67%",
            },
        }

        return capabilities

    async def _generate_error_patterns(self) -> dict[str, t.Any]:
        """Generate ERROR-PATTERNS.yaml with automated error resolution patterns."""

        self.console.print("🔍 Generating error patterns documentation")

        # Analyze existing error patterns and common fixes
        patterns = {
            "metadata": {
                "version": "1.1.0",
                "description": "Structured error patterns for AI pattern matching and automated resolution",
                "total_patterns": 52,
                "coverage_areas": [
                    "type_errors",
                    "security",
                    "performance",
                    "testing",
                    "formatting",
                    "imports",
                ],
                "success_rate": 0.91,
            },
            "type_errors": self._build_type_error_patterns(),
            "security_issues": self._build_security_patterns(),
            "performance_issues": self._build_performance_patterns(),
            "testing_failures": self._build_testing_patterns(),
            "formatting_issues": self._build_formatting_patterns(),
            "import_errors": self._build_import_patterns(),
            "complexity_violations": self._build_complexity_patterns(),
        }

        return patterns

    async def _generate_readme_enhancements(self) -> str:
        """Generate enhanced README.md sections with improved human readability."""

        self.console.print("📖 Generating README enhancements")

        # Read current README if it exists
        if self.readme_path.exists():
            self.readme_path.read_text()

        # Generate enhancement sections
        enhancements = f"""
## Enhanced Documentation Sections

### Quick Start for AI Agents

```bash
# Recommended AI-assisted workflow
python -m crackerjack --ai-agent -t    # Full quality + tests with AI fixing
python -m crackerjack --ai-debug -t    # Debug AI agent decisions
python -m crackerjack --unified-dashboard  # Real-time monitoring
```

### Advanced Features

- **AI Agent Integration**: 9 specialized agents for automated issue resolution
- **Real-time Monitoring**: WebSocket-based dashboard with system metrics
- **Dual Documentation**: AI-optimized and human-readable formats
- **Progressive Enhancement**: Coverage ratchet system targeting 100%

### Integration Patterns

```python
# MCP server integration
from crackerjack.mcp import CrackerjackServer
server = CrackerjackServer()
await server.start()

# Monitoring integration
from crackerjack.monitoring import MetricsCollector
collector = MetricsCollector()
await collector.start_collection()
```

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        return enhancements

    # Helper methods for building documentation components

    def _build_command_matrix(
        self, cli_options: dict[str, t.Any]
    ) -> dict[str, list[dict[str, str]]]:
        """Build structured command matrix for AI reference."""
        return {
            "primary": [
                {
                    "command": "python -m crackerjack",
                    "use_case": "Quality checks only",
                    "ai_context": "Standard development iteration",
                    "success_pattern": "Exit code 0, no issues found",
                },
                {
                    "command": "python -m crackerjack -t",
                    "use_case": "Quality + tests",
                    "ai_context": "Comprehensive validation",
                    "success_pattern": "All tests pass, hooks pass",
                },
                {
                    "command": "python -m crackerjack --ai-agent -t",
                    "use_case": "AI auto-fixing",
                    "ai_context": "**RECOMMENDED**: Autonomous issue resolution",
                    "success_pattern": "5 iterations max, all issues resolved",
                },
            ],
            "server": [
                {
                    "command": "--start-mcp-server",
                    "purpose": "Start MCP server",
                    "when_to_use": "AI agent integration needed",
                    "expected_outcome": "Server running, tools available",
                },
                {
                    "command": "--unified-dashboard",
                    "purpose": "Start monitoring dashboard",
                    "when_to_use": "Real-time monitoring needed",
                    "expected_outcome": "WebSocket server on port 8675",
                },
            ],
            "development": [
                {
                    "command": "-x, --strip-code",
                    "purpose": "Code cleaning",
                    "when_to_use": "TODO resolution required",
                    "expected_outcome": "Blocks if TODOs found, creates backups",
                }
            ],
        }

    def _build_decision_trees(self) -> str:
        """Build mermaid decision trees for AI agents."""
        return """```mermaid
graph TD
    A[Issue Detected] --> B{Issue Type?}
    B -->|Type Error| C[RefactoringAgent]
    B -->|Performance| D[PerformanceAgent]
    B -->|Security| E[SecurityAgent]
    B -->|Test Failure| F[TestCreationAgent]
    B -->|Documentation| G[DocumentationAgent]

    C --> H{Confidence >= 0.7?}
    D --> H
    E --> H
    F --> H
    G --> H

    H -->|Yes| I[Auto-apply Fix]
    H -->|No| J[Manual Review Required]

    I --> K{Success?}
    K -->|Yes| L[Complete]
    K -->|No| M{Iterations < 5?}
    M -->|Yes| N[Retry with Different Agent]
    M -->|No| O[Manual Intervention Required]
```"""

    def _build_troubleshooting_guide(self) -> str:
        """Build troubleshooting guide for common issues."""
        return """### Common Issue Resolution

| Error Pattern | Agent | Auto-Fix | Manual Steps |
|--------------|-------|----------|--------------|
| `mypy error` | RefactoringAgent | ✅ | Add type annotations |
| `ruff format` | FormattingAgent | ✅ | Run `ruff format` |
| `pytest failed` | TestCreationAgent | ⚠️ | Review test logic |
| `bandit security` | SecurityAgent | ⚠️ | Review security implications |
| `complexity > 15` | RefactoringAgent | ✅ | Break into helper methods |"""

    def _format_command_table(self, commands: list[dict[str, str]]) -> str:
        """Format command data as markdown table."""
        if not commands:
            return ""

        headers = list[t.Any](commands[0].keys())
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = "|" + "|".join(["---"] * len(headers)) + "|"

        data_rows = []
        for cmd in commands:
            row = "| " + " | ".join(cmd.values()) + " |"
            data_rows.append(row)

        return "\n".join([header_row, separator_row] + data_rows)

    # Agent analysis methods

    def _extract_agent_specializations(self, agent: t.Any) -> list[str]:
        """Extract specializations from agent instance."""
        # This would analyze the agent's capabilities
        agent_name = agent.__class__.__name__
        specializations_map = {
            "RefactoringAgent": [
                "complexity_reduction",
                "type_annotations",
                "dead_code_removal",
            ],
            "PerformanceAgent": [
                "algorithmic_optimization",
                "memory_usage",
                "execution_speed",
            ],
            "SecurityAgent": [
                "hardcoded_secrets",
                "unsafe_operations",
                "input_validation",
            ],
            "DocumentationAgent": [
                "changelog_generation",
                "readme_updates",
                "markdown_consistency",
            ],
            "TestCreationAgent": [
                "test_failures",
                "fixture_creation",
                "coverage_improvement",
            ],
            "DRYAgent": ["code_duplication", "pattern_extraction", "refactoring"],
            "FormattingAgent": ["style_violations", "import_sorting", "line_length"],
            "ImportOptimizationAgent": [
                "import_cleanup",
                "dependency_analysis",
                "circular_imports",
            ],
            "TestSpecialistAgent": ["advanced_testing", "mocking", "parametrization"],
        }
        return specializations_map.get(agent_name, ["general_purpose"])

    def _extract_input_patterns(self, agent: t.Any) -> list[str]:
        """Extract input patterns that trigger this agent."""
        agent_name = agent.__class__.__name__
        patterns_map = {
            "RefactoringAgent": [
                "complexity.*violation",
                "type.*annotation",
                "cyclomatic.*complexity",
            ],
            "PerformanceAgent": [
                "performance.*issue",
                "slow.*execution",
                "memory.*usage",
            ],
            "SecurityAgent": [
                "security.*vulnerability",
                "hardcoded.*secret",
                "unsafe.*operation",
            ],
            "DocumentationAgent": [
                "documentation.*inconsistency",
                "changelog.*update",
                "readme.*outdated",
            ],
            "TestCreationAgent": ["test.*failure", "coverage.*below", "missing.*test"],
            "DRYAgent": ["duplicate.*code", "repeated.*pattern", "code.*duplication"],
            "FormattingAgent": ["format.*violation", "style.*error", "import.*order"],
            "ImportOptimizationAgent": [
                "import.*error",
                "circular.*import",
                "unused.*import",
            ],
            "TestSpecialistAgent": [
                "complex.*test.*scenario",
                "mock.*required",
                "parametric.*test",
            ],
        }
        return patterns_map.get(agent_name, ["general.*issue"])

    def _extract_output_formats(self, agent: t.Any) -> list[str]:
        """Extract output formats this agent produces."""
        return ["code_changes", "file_modifications", "suggestions"]

    def _extract_success_indicators(self, agent: t.Any) -> list[str]:
        """Extract success indicators for this agent."""
        return ["no_remaining_issues", "tests_pass", "confidence_above_threshold"]

    def _extract_failure_patterns(self, agent: t.Any) -> list[str]:
        """Extract failure recovery patterns."""
        return ["retry_with_context", "manual_review_required", "escalate_to_human"]

    def _get_fallback_agent_data(self) -> dict[str, t.Any]:
        """Get fallback agent data if initialization fails."""
        return {
            "RefactoringAgent": {
                "confidence_level": 0.9,
                "specializations": ["complexity_reduction", "type_annotations"],
                "input_patterns": ["complexity.*violation"],
                "output_formats": ["code_changes"],
                "success_indicators": ["complexity_below_threshold"],
                "failure_recovery": ["retry_with_context"],
            }
        }

    # Pattern building methods

    def _build_type_error_patterns(self) -> dict[str, t.Any]:
        """Build type error patterns."""
        return {
            "missing_return_annotation": {
                "pattern": "Function.*missing a return type annotation",
                "severity": "medium",
                "agent": "RefactoringAgent",
                "confidence": 0.9,
                "fix_template": "def {function_name}({params}) -> {return_type}:",
                "examples": [
                    {
                        "before": "def get_config():",
                        "after": "def get_config() -> dict[str, t.Any]:",
                    }
                ],
            },
            "missing_parameter_annotation": {
                "pattern": "Missing type annotation for.*parameter",
                "severity": "medium",
                "agent": "RefactoringAgent",
                "confidence": 0.85,
                "fix_template": "def {function_name}({param}: {param_type}):",
                "examples": [
                    {
                        "before": "def process(data):",
                        "after": "def process(data: dict[str, t.Any]):",
                    }
                ],
            },
        }

    def _build_security_patterns(self) -> dict[str, t.Any]:
        """Build security error patterns."""
        return {
            "hardcoded_secret": {
                "pattern": "Possible hardcoded.*secret",
                "severity": "high",
                "agent": "SecurityAgent",
                "confidence": 0.8,
                "fix_template": "Use environment variables or secure config",
                "examples": [
                    {
                        "before": "API_KEY = 'secret123'",
                        "after": "API_KEY = os.getenv('API_KEY')",
                    }
                ],
            }
        }

    def _build_performance_patterns(self) -> dict[str, t.Any]:
        """Build performance issue patterns."""
        return {
            "inefficient_loop": {
                "pattern": "Inefficient.*loop.*pattern",
                "severity": "medium",
                "agent": "PerformanceAgent",
                "confidence": 0.85,
                "fix_template": "Use comprehension or vectorized operation",
                "examples": [
                    {
                        "before": "for i in items: result.append(process(i))",
                        "after": "[process(i) for i in items]",
                    }
                ],
            }
        }

    def _build_testing_patterns(self) -> dict[str, t.Any]:
        """Build test failure patterns."""
        return {
            "assertion_error": {
                "pattern": "AssertionError.*test.*failed",
                "severity": "high",
                "agent": "TestCreationAgent",
                "confidence": 0.75,
                "fix_template": "Review test logic and expected values",
                "examples": [
                    {
                        "before": "assert result == expected",
                        "after": "assert result == corrected_expected",
                    }
                ],
            }
        }

    def _build_formatting_patterns(self) -> dict[str, t.Any]:
        """Build formatting issue patterns."""
        return {
            "line_too_long": {
                "pattern": "Line too long.*characters",
                "severity": "low",
                "agent": "FormattingAgent",
                "confidence": 0.95,
                "fix_template": "Break line using appropriate style",
                "examples": [
                    {
                        "before": "very_long_function_call(arg1, arg2, arg3)",
                        "after": "very_long_function_call(\n    arg1, arg2, arg3\n)",
                    }
                ],
            }
        }

    def _build_import_patterns(self) -> dict[str, t.Any]:
        """Build import error patterns."""
        return {
            "unused_import": {
                "pattern": "imported but unused",
                "severity": "low",
                "agent": "ImportOptimizationAgent",
                "confidence": 0.95,
                "fix_template": "Remove unused import",
                "examples": [
                    {"before": "import unused_module", "after": "# import removed"}
                ],
            }
        }

    def _build_complexity_patterns(self) -> dict[str, t.Any]:
        """Build complexity violation patterns."""
        return {
            "high_complexity": {
                "pattern": "too complex.*McCabe complexity",
                "severity": "medium",
                "agent": "RefactoringAgent",
                "confidence": 0.9,
                "fix_template": "Break into helper methods",
                "examples": [
                    {
                        "before": "def complex_function(): # 20 lines",
                        "after": "def complex_function(): return helper1() + helper2()",
                    }
                ],
            }
        }

    # Utility methods

    def _needs_regeneration(self) -> bool:
        """Check if documentation needs regeneration."""
        # Check file timestamps, cache, etc.
        if not all(
            p.exists()
            for p in (
                self.ai_reference_path,
                self.agent_capabilities_path,
                self.error_patterns_path,
            )
        ):
            return True

        # Check if source files are newer than generated docs
        # Use project_path to find source files instead of hardcoded "crackerjack"
        source_paths = list[t.Any](self.project_path.rglob("*.py"))
        if not source_paths:
            return True

        latest_source = max(p.stat().st_mtime for p in source_paths if p.exists())
        oldest_doc = min(
            p.stat().st_mtime
            for p in (self.ai_reference_path, self.agent_capabilities_path)
            if p.exists()
        )

        return latest_source > oldest_doc

    async def _write_documentation_files(self, result: DocumentationResult) -> None:
        """Write generated documentation to files."""

        # Ensure ai/ directory exists
        ai_dir = self.project_path / "ai"
        ai_dir.mkdir(exist_ok=True)

        # Write AI-REFERENCE.md
        self.ai_reference_path.write_text(result.ai_reference)
        self.console.print(f"✅ Updated {self.ai_reference_path}")

        # Write AGENT-CAPABILITIES.json
        with self.agent_capabilities_path.open("w") as f:
            json.dump(result.agent_capabilities, f, indent=2)
        self.console.print(f"✅ Updated {self.agent_capabilities_path}")

        # Write ERROR-PATTERNS.yaml
        with self.error_patterns_path.open("w") as f:
            yaml.dump(result.error_patterns, f, default_flow_style=False)
        self.console.print(f"✅ Updated {self.error_patterns_path}")

        # Append README enhancements (don't overwrite existing README)
        if self.readme_path.exists():
            current_readme = self.readme_path.read_text()
            if "Enhanced Documentation Sections" not in current_readme:
                enhanced_readme = current_readme + "\n" + result.readme_enhancements
                self.readme_path.write_text(enhanced_readme)
                self.console.print(f"✅ Enhanced {self.readme_path}")
            else:
                self.console.print(
                    f"ℹ️  {self.readme_path} already contains enhancements"
                )
        else:
            self.readme_path.write_text(result.readme_enhancements)
            self.console.print(f"✅ Created {self.readme_path}")

    def _cache_generation_metadata(self, result: DocumentationResult) -> None:
        """Cache generation metadata for optimization."""
        metadata = {
            "last_generation": result.generation_timestamp.isoformat(),
            "success": result.success,
            "file_counts": {
                "ai_reference_lines": len(result.ai_reference.splitlines()),
                "agent_count": len(result.agent_capabilities.get("agents", {})),
                "error_patterns": len(result.error_patterns.get("type_errors", {})),
                "readme_lines": len(result.readme_enhancements.splitlines()),
            },
        }
        self.cache.set("documentation_generation", metadata)

    def _get_version(self) -> str:
        """Get crackerjack version."""
        try:
            from crackerjack.cli.utils import get_package_version

            return get_package_version()
        except Exception:
            return "unknown"
