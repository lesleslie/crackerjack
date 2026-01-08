import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.services.incremental_executor import IncrementalExecutor


@dataclass
class FilterConfig:
    tool_name: str | None = None
    changed_only: bool = False
    file_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class FilterResult:
    total_tools: int
    filtered_tools: list[str]
    skipped_tools: list[str]
    total_files: int
    filtered_files: list[Path]
    skipped_files: list[Path]
    filter_effectiveness: float

    @property
    def tools_filtered_out(self) -> int:
        return len(self.skipped_tools)

    @property
    def files_filtered_out(self) -> int:
        return len(self.skipped_files)


class ToolFilter:
    def __init__(
        self,
        config: FilterConfig,
        executor: IncrementalExecutor | None = None,
    ):
        self.config = config
        self.executor = executor

    def filter_tools(
        self,
        available_tools: list[str],
    ) -> FilterResult:
        if self.config.tool_name:
            if self.config.tool_name in available_tools:
                filtered = [self.config.tool_name]
                skipped = [t for t in available_tools if t != self.config.tool_name]
            else:
                filtered = []
                skipped = available_tools.copy()
        else:
            filtered = available_tools.copy()
            skipped = []

        total_tools = len(available_tools)
        effectiveness = (len(skipped) / total_tools * 100) if total_tools > 0 else 0.0

        return FilterResult(
            total_tools=total_tools,
            filtered_tools=filtered,
            skipped_tools=skipped,
            total_files=0,
            filtered_files=[],
            skipped_files=[],
            filter_effectiveness=effectiveness,
        )

    def filter_files(
        self,
        tool_name: str,
        all_files: list[Path],
    ) -> FilterResult:
        filtered_files = all_files.copy()
        skipped_files: list[Path] = []

        if self.config.changed_only and self.executor:
            changed_files = self.executor.get_changed_files(tool_name, all_files)
            skipped_files = [f for f in all_files if f not in changed_files]
            filtered_files = changed_files

        if self.config.file_patterns:
            pattern_filtered = self._apply_patterns(
                filtered_files,
                self.config.file_patterns,
                include=True,
            )
            new_skipped = [f for f in filtered_files if f not in pattern_filtered]
            skipped_files.extend(new_skipped)
            filtered_files = pattern_filtered

        if self.config.exclude_patterns:
            exclude_filtered = self._apply_patterns(
                filtered_files,
                self.config.exclude_patterns,
                include=False,
            )
            new_skipped = [f for f in filtered_files if f not in exclude_filtered]
            skipped_files.extend(new_skipped)
            filtered_files = exclude_filtered

        total_files = len(all_files)
        effectiveness = (
            (len(skipped_files) / total_files * 100) if total_files > 0 else 0.0
        )

        return FilterResult(
            total_tools=1,
            filtered_tools=[tool_name],
            skipped_tools=[],
            total_files=total_files,
            filtered_files=filtered_files,
            skipped_files=skipped_files,
            filter_effectiveness=effectiveness,
        )

    def _apply_patterns(
        self,
        files: list[Path],
        patterns: list[str],
        include: bool,
    ) -> list[Path]:
        matching_files: set[Path] = set()

        for pattern in patterns:
            for file in files:
                if fnmatch.fnmatch(file.name, pattern) or fnmatch.fnmatch(
                    str(file), pattern
                ):
                    matching_files.add(file)

        if include:
            return [f for f in files if f in matching_files]

        return [f for f in files if f not in matching_files]

    def should_run_tool(self, tool_name: str) -> bool:
        if self.config.tool_name is None:
            return True

        return tool_name == self.config.tool_name

    def get_filtered_files(
        self,
        tool_name: str,
        all_files: list[Path],
    ) -> list[Path]:
        result = self.filter_files(tool_name, all_files)
        return result.filtered_files

    def estimate_time_savings(
        self,
        tool_execution_times: dict[str, float],
        file_execution_time_per_file: float = 0.1,
    ) -> dict[str, float]:
        if not self.config.tool_name and not self.config.changed_only:
            return {
                "total_time_baseline": sum(tool_execution_times.values()),
                "total_time_filtered": sum(tool_execution_times.values()),
                "time_saved": 0.0,
                "percent_saved": 0.0,
            }

        baseline_time = sum(tool_execution_times.values())

        if self.config.tool_name:
            filtered_time = tool_execution_times.get(self.config.tool_name, 0.0)
        else:
            filtered_time = baseline_time

        time_saved = baseline_time - filtered_time
        percent_saved = (time_saved / baseline_time * 100) if baseline_time > 0 else 0.0

        return {
            "total_time_baseline": baseline_time,
            "total_time_filtered": filtered_time,
            "time_saved": time_saved,
            "percent_saved": percent_saved,
        }

    def generate_filter_summary(
        self,
        tool_result: FilterResult | None = None,
        file_result: FilterResult | None = None,
    ) -> str:
        lines = ["# Filter Summary", ""]

        if tool_result:
            lines.extend(
                [
                    "## Tool Filtering",
                    f"- Total Tools: {tool_result.total_tools}",
                    f"- Tools to Run: {len(tool_result.filtered_tools)}",
                    f"- Tools Skipped: {len(tool_result.skipped_tools)}",
                    f"- Effectiveness: {tool_result.filter_effectiveness:.1f}%",
                    "",
                ]
            )

            if tool_result.filtered_tools:
                lines.append("**Running:**")
                for tool in tool_result.filtered_tools:
                    lines.append(f" - {tool}")
                lines.append("")

        if file_result:
            lines.extend(
                [
                    "## File Filtering",
                    f"- Total Files: {file_result.total_files}",
                    f"- Files to Process: {len(file_result.filtered_files)}",
                    f"- Files Skipped: {len(file_result.skipped_files)}",
                    f"- Effectiveness: {file_result.filter_effectiveness:.1f}%",
                    "",
                ]
            )

        return "\n".join(lines)


def create_tool_only_filter(tool_name: str) -> ToolFilter:
    config = FilterConfig(tool_name=tool_name)
    return ToolFilter(config=config)


def create_changed_files_filter(
    executor: IncrementalExecutor,
) -> ToolFilter:
    config = FilterConfig(changed_only=True)
    return ToolFilter(config=config, executor=executor)


def create_combined_filter(
    tool_name: str,
    executor: IncrementalExecutor,
) -> ToolFilter:
    config = FilterConfig(tool_name=tool_name, changed_only=True)
    return ToolFilter(config=config, executor=executor)
