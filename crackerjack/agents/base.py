import asyncio
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueType(Enum):
    FORMATTING = "formatting"
    TYPE_ERROR = "type_error"
    SECURITY = "security"
    TEST_FAILURE = "test_failure"
    IMPORT_ERROR = "import_error"
    COMPLEXITY = "complexity"
    DEAD_CODE = "dead_code"
    DEPENDENCY = "dependency"
    DRY_VIOLATION = "dry_violation"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    TEST_ORGANIZATION = "test_organization"
    COVERAGE_IMPROVEMENT = "coverage_improvement"
    REGEX_VALIDATION = "regex_validation"
    SEMANTIC_CONTEXT = "semantic_context"


@dataclass
class Issue:
    id: str
    type: IssueType
    severity: Priority
    message: str
    file_path: str | None = None
    line_number: int | None = None
    details: list[str] = field(default_factory=list)
    stage: str = "unknown"


@dataclass
class FixResult:
    success: bool
    confidence: float
    fixes_applied: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    def merge_with(self, other: "FixResult") -> "FixResult":
        return FixResult(
            success=self.success and other.success,
            confidence=max(self.confidence, other.confidence),
            fixes_applied=self.fixes_applied + other.fixes_applied,
            remaining_issues=list[t.Any](
                set[t.Any](self.remaining_issues + other.remaining_issues)
            ),
            recommendations=self.recommendations + other.recommendations,
            files_modified=list[t.Any](
                set[t.Any](self.files_modified + other.files_modified)
            ),
        )


@dataclass
class AgentContext:
    project_path: Path
    temp_dir: Path | None = None
    config: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    session_id: str | None = None

    subprocess_timeout: int = 300
    max_file_size: int = 10_000_000

    def get_file_content(self, file_path: str | Path) -> str | None:
        try:
            path = Path(file_path)
            if not path.is_file():
                return None
            if path.stat().st_size > self.max_file_size:
                return None
            return path.read_text(encoding="utf-8")
        except Exception:
            return None

    def write_file_content(self, file_path: str | Path, content: str) -> bool:
        try:
            path = Path(file_path)
            path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False


class SubAgent(ABC):
    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self.name = self.__class__.__name__

    @abstractmethod
    async def can_handle(self, issue: Issue) -> float:
        pass

    @abstractmethod
    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        pass

    @abstractmethod
    def get_supported_types(self) -> set[IssueType]:
        pass

    async def run_command(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd or self.context.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout or self.context.subprocess_timeout,
            )

            return (
                process.returncode or 0,
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else "",
            )
        except TimeoutError:
            return (-1, "", "Command timed out")
        except Exception as e:
            return (-1, "", f"Command failed: {e}")

    def log(self, message: str, level: str = "INFO") -> None:
        pass

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        return {"strategy": "default", "confidence": 0.5}

    def get_cached_patterns(self) -> dict[str, t.Any]:
        return {}


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, type[SubAgent]] = {}

    def register(self, agent_class: type[SubAgent]) -> None:
        self._agents[agent_class.__name__] = agent_class

    def create_all(self, context: AgentContext) -> list[SubAgent]:
        return [agent_cls(context) for agent_cls in self._agents.values()]


agent_registry = AgentRegistry()
