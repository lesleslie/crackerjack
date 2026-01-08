import typing as t
from dataclasses import dataclass
from pathlib import Path

from ._base import BaseRustToolAdapter, Issue, ToolResult

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext


@dataclass
class DeadCodeIssue(Issue):
    severity: str = "warning"
    issue_type: str = "unknown"
    name: str = "unknown"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, t.Any]:
        base_dict = super().to_dict()
        base_dict.update(
            {
                "issue_type": self.issue_type,
                "name": self.name,
                "confidence": self.confidence,
            }
        )
        return base_dict


class SkylosAdapter(BaseRustToolAdapter):
    def __init__(
        self,
        context: "ExecutionContext",
        confidence_threshold: int = 99,
        web_dashboard_port: int = 5090,
    ) -> None:
        super().__init__(context)
        self.confidence_threshold = confidence_threshold
        self.web_dashboard_port = web_dashboard_port

    def get_tool_name(self) -> str:
        return "skylos"

    def supports_json_output(self) -> bool:
        return True

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        args = [
            "uv",
            "run",
            "skylos",
            "--confidence",
            str(max(95, self.confidence_threshold)),
        ]

        if self._should_use_json_output():
            args.append("--json")

        if self.context.interactive:
            args.extend(["--web", "--port", str(self.web_dashboard_port)])

        if target_files:
            package_files = self._filter_package_files(target_files)
            if package_files:
                args.extend(str(f) for f in package_files)
            else:
                package_target = self._determine_package_target()
                args.append(package_target)
        else:
            package_target = self._determine_package_target()
            args.append(package_target)

        return args

    def _determine_package_target(self) -> str:
        from pathlib import Path

        cwd = Path.cwd()
        package_name = self._get_package_name_from_pyproject(cwd)

        if not package_name:
            package_name = self._find_package_directory_with_init(cwd)

        if not package_name:
            package_name = "crackerjack"

        return f"./{package_name}"

    def _get_package_name_from_pyproject(self, cwd: Path) -> str | None:
        pyproject_path = cwd / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        import tomllib
        from contextlib import suppress

        with suppress(Exception):
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                project_name = data.get("project", {}).get("name")
                if project_name:
                    return project_name.replace("-", "_")
        return None

    def _find_package_directory_with_init(self, cwd: Path) -> str | None:
        excluded = {"tests", "docs", ".venv", "venv", "build", "dist"}

        for item in cwd.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                if item.name not in excluded:
                    return item.name
        return None

    def _filter_package_files(self, target_files: list[Path]) -> list[Path]:
        from pathlib import Path

        cwd = Path.cwd()
        package_name = self._get_package_name_from_pyproject(cwd)
        if not package_name:
            package_name = self._find_package_directory_with_init(cwd)
        if not package_name:
            package_name = "crackerjack"

        excluded_dirs = {
            "tests",
            "test",
            "docs",
            "doc",
            "scripts",
            "script",
            "examples",
            "example",
            ".venv",
            "venv",
            "build",
            "dist",
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "archive",
            ".archive",
        }

        package_files = []
        for file_path in target_files:
            abs_path = file_path.resolve() if not file_path.is_absolute() else file_path

            try:
                rel_path = abs_path.relative_to(cwd)
                top_level_dir = rel_path.parts[0] if rel_path.parts else ""

                if top_level_dir == package_name and top_level_dir not in excluded_dirs:
                    package_files.append(file_path)
            except ValueError:
                continue

        return package_files

    def parse_output(self, output: str) -> ToolResult:
        if self._should_use_json_output():
            return self._parse_json_output(output)
        return self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> ToolResult:
        data = self._parse_json_output_safe(output)
        if data is None:
            return self._create_error_result(
                "Invalid JSON output from Skylos", raw_output=output
            )

        try:
            issues: list[Issue] = [
                DeadCodeIssue(
                    file_path=Path(item["file"]),
                    line_number=item.get("line", 1),
                    message=f"Dead {item['type']}: {item['name']}",
                    severity="warning",
                    issue_type=item["type"],
                    name=item["name"],
                    confidence=item.get("confidence", 0.0),
                )
                for item in data.get("dead_code", [])
            ]

            success = len(issues) == 0

            return ToolResult(
                success=success,
                issues=issues,
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        except (KeyError, TypeError, ValueError) as e:
            return self._create_error_result(
                f"Failed to parse Skylos JSON output: {e}", raw_output=output
            )

    def _parse_text_output(self, output: str) -> ToolResult:
        issues: list[Issue] = []

        if not output.strip():
            return ToolResult(
                success=True,
                issues=[],
                raw_output=output,
                tool_version=self.get_tool_version(),
            )

        for line in output.strip().split("\\n"):
            line = line.strip()
            if not line:
                continue

            issue = self._parse_text_line(line)
            if issue:
                issues.append(issue)

        success = len(issues) == 0

        return ToolResult(
            success=success,
            issues=issues,
            raw_output=output,
            tool_version=self.get_tool_version(),
        )

    def _parse_text_line(self, line: str) -> DeadCodeIssue | None:
        try:
            basic_info = self._extract_basic_line_info(line)
            if not basic_info:
                return None

            file_path, line_number, message_part = basic_info
            issue_details = self._extract_issue_details(message_part)
            confidence = self._extract_confidence(message_part)

            return DeadCodeIssue(
                file_path=file_path,
                line_number=line_number,
                message=f"Dead {issue_details['type']}: {issue_details['name']}",
                severity="warning",
                issue_type=issue_details["type"],
                name=issue_details["name"],
                confidence=confidence,
            )

        except (IndexError, ValueError):
            return None

    def _extract_basic_line_info(self, line: str) -> tuple[Path, int, str] | None:
        if ":" not in line:
            return None

        parts = line.split(":", 2)
        if len(parts) < 3:
            return None

        file_path = Path(parts[0].strip())
        try:
            line_number = int(parts[1].strip())
        except ValueError:
            line_number = 1

        message_part = parts[2].strip()
        return file_path, line_number, message_part

    def _extract_issue_details(self, message_part: str) -> dict[str, str]:
        issue_type = "unknown"
        name = "unknown"

        lower_message = message_part.lower()

        if "unused import" in lower_message:
            issue_type = "import"
            name = self._extract_name_from_quotes(message_part)
        elif "unused function" in lower_message:
            issue_type = "function"
            name = self._extract_name_from_quotes(message_part)
        elif "unused class" in lower_message:
            issue_type = "class"
            name = self._extract_name_from_quotes(message_part)

        return {"type": issue_type, "name": name}

    def _extract_name_from_quotes(self, message_part: str) -> str:
        quoted_parts = message_part.split("'")
        if len(quoted_parts) >= 2:
            return quoted_parts[1]
        return "unknown"

    def _extract_confidence(self, message_part: str) -> float:
        if "(confidence:" not in message_part:
            return float(self.confidence_threshold)

        try:
            conf_part = message_part.split("(confidence:")[1].split(")")[0]
            return float(conf_part.strip().replace("%", ""))
        except (ValueError, IndexError):
            return float(self.confidence_threshold)
