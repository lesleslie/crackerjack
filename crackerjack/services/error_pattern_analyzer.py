"""Error pattern analysis service for heat map visualizations."""

import json
import logging
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ErrorPattern:
    """Represents an error pattern for visualization."""

    error_type: str
    message: str
    file_path: str
    function_name: str | None
    line_number: int | None
    count: int
    severity: str  # low, medium, high, critical
    first_seen: datetime
    last_seen: datetime
    trend: str  # increasing, decreasing, stable
    confidence: float  # 0.0 to 1.0
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "file_path": self.file_path,
            "function_name": self.function_name,
            "line_number": self.line_number,
            "count": self.count,
            "severity": self.severity,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "trend": self.trend,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class HeatMapCell:
    """Represents a cell in the heat map."""

    x: str  # file_path or time period
    y: str  # error_type or function_name
    value: float  # intensity/count
    color_intensity: float  # 0.0 to 1.0
    tooltip_data: dict[str, t.Any]
    severity: str

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "value": self.value,
            "color_intensity": self.color_intensity,
            "tooltip_data": self.tooltip_data,
            "severity": self.severity,
        }


@dataclass
class HeatMapData:
    """Complete heat map visualization data."""

    cells: list[HeatMapCell]
    x_labels: list[str]
    y_labels: list[str]
    title: str
    subtitle: str
    max_value: float
    min_value: float
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cells": [cell.to_dict() for cell in self.cells],
            "x_labels": self.x_labels,
            "y_labels": self.y_labels,
            "title": self.title,
            "subtitle": self.subtitle,
            "max_value": self.max_value,
            "min_value": self.min_value,
            "generated_at": self.generated_at.isoformat(),
        }


class ErrorPatternAnalyzer:
    """Analyzes error patterns and generates heat map visualizations."""

    def __init__(self, project_root: Path):
        """Initialize with project root directory."""
        self.project_root = Path(project_root)
        self.error_patterns: list[ErrorPattern] = []

    def analyze_error_patterns(
        self,
        days: int = 30,
        min_occurrences: int = 2,
    ) -> list[ErrorPattern]:
        """Analyze error patterns from various sources."""
        logger.info(f"Analyzing error patterns for last {days} days")

        # Collect and process errors
        errors = self._collect_all_errors()
        self.error_patterns = self._process_error_data(errors, min_occurrences)
        self._finalize_pattern_analysis()

        logger.info(f"Found {len(self.error_patterns)} error patterns")
        return self.error_patterns

    def _collect_all_errors(self) -> list[dict[str, t.Any]]:
        """Collect errors from all available sources."""
        errors: list[dict[str, t.Any]] = []
        errors.extend(self._analyze_test_failures())
        errors.extend(self._analyze_lint_errors())
        errors.extend(self._analyze_git_history())
        errors.extend(self._analyze_log_files())
        return errors

    def _process_error_data(
        self, errors: list[dict[str, t.Any]], min_occurrences: int
    ) -> list[ErrorPattern]:
        """Process collected errors into patterns."""
        pattern_groups = self._group_similar_errors(errors)
        return self._create_error_patterns(pattern_groups, min_occurrences)

    def _finalize_pattern_analysis(self) -> None:
        """Apply final analysis steps to error patterns."""
        self._calculate_error_trends()
        self._assign_severity_levels()

    def generate_file_error_heatmap(self) -> HeatMapData:
        """Generate heat map showing errors by file."""

        def _make_float_defaultdict() -> defaultdict[str, float]:
            return defaultdict(float)

        file_error_counts: defaultdict[str, defaultdict[str, float]] = defaultdict(
            _make_float_defaultdict
        )
        max_value = 0.0

        for pattern in self.error_patterns:
            file_path = self._get_relative_path(pattern.file_path)
            error_type = pattern.error_type
            count = pattern.count

            file_error_counts[file_path][error_type] += float(count)
            max_value = max(max_value, file_error_counts[file_path][error_type])

        # Create heat map cells
        cells = []
        files = sorted(file_error_counts.keys())
        error_types = sorted(
            {
                error_type
                for file_errors in file_error_counts.values()
                for error_type in file_errors.keys()
            }
        )

        for file_path in files:
            for error_type in error_types:
                count = file_error_counts[file_path].get(error_type, 0)
                if count > 0:
                    intensity: float = count / max_value if max_value > 0 else 0.0
                    severity = self._get_severity_for_type(error_type)

                    cells.append(
                        HeatMapCell(
                            x=file_path,
                            y=error_type,
                            value=count,
                            color_intensity=intensity,
                            tooltip_data={
                                "file": file_path,
                                "error_type": error_type,
                                "count": count,
                                "severity": severity,
                            },
                            severity=severity,
                        )
                    )

        return HeatMapData(
            cells=cells,
            x_labels=files,
            y_labels=error_types,
            title="Error Distribution by File",
            subtitle=f"Showing {len(self.error_patterns)} error patterns across {len(files)} files",
            max_value=max_value,
            min_value=0.0,
        )

    def generate_temporal_heatmap(self, time_buckets: int = 24) -> HeatMapData:
        """Generate heat map showing errors over time."""
        time_labels, time_buckets_data, bucket_size = self._create_time_buckets(
            time_buckets
        )
        temporal_counts, max_value = self._count_errors_by_time(
            time_labels, time_buckets_data, bucket_size
        )
        cells, error_types = self._create_temporal_heatmap_cells(
            time_labels, temporal_counts, max_value
        )

        return HeatMapData(
            cells=cells,
            x_labels=time_labels,
            y_labels=error_types,
            title="Error Patterns Over Time",
            subtitle=f"24-hour view of {len(self.error_patterns)} error patterns",
            max_value=max_value,
            min_value=0.0,
        )

    def _create_time_buckets(
        self, time_buckets: int
    ) -> tuple[list[str], list[datetime], timedelta]:
        """Create time buckets for temporal analysis."""
        now = datetime.now()
        bucket_size = timedelta(hours=24 // time_buckets)

        time_labels = []
        time_buckets_data = []
        for i in range(time_buckets):
            bucket_start = now - timedelta(days=30) + (i * bucket_size)
            time_labels.append(bucket_start.strftime("%m-%d %H:%M"))
            time_buckets_data.append(bucket_start)

        return time_labels, time_buckets_data, bucket_size

    def _count_errors_by_time(
        self,
        time_labels: list[str],
        time_buckets_data: list[datetime],
        bucket_size: timedelta,
    ) -> tuple[defaultdict[str, defaultdict[str, float]], float]:
        """Count errors by time bucket and type."""

        def _make_float_defaultdict_temporal() -> defaultdict[str, float]:
            return defaultdict(float)

        temporal_counts: defaultdict[str, defaultdict[str, float]] = defaultdict(
            _make_float_defaultdict_temporal
        )
        max_value = 0.0

        for pattern in self.error_patterns:
            bucket_idx = self._find_time_bucket(
                pattern.last_seen, time_buckets_data, bucket_size
            )
            if bucket_idx is not None:
                bucket_label = time_labels[bucket_idx]
                error_type = pattern.error_type
                temporal_counts[bucket_label][error_type] += pattern.count
                max_value = max(max_value, temporal_counts[bucket_label][error_type])

        return temporal_counts, max_value

    def _find_time_bucket(
        self,
        error_time: datetime,
        time_buckets_data: list[datetime],
        bucket_size: timedelta,
    ) -> int | None:
        """Find which time bucket an error belongs to."""
        for i, bucket_time in enumerate(time_buckets_data):
            if bucket_time <= error_time <= bucket_time + bucket_size:
                return i
        return None

    def _create_temporal_heatmap_cells(
        self,
        time_labels: list[str],
        temporal_counts: defaultdict[str, defaultdict[str, float]],
        max_value: float,
    ) -> tuple[list[HeatMapCell], list[str]]:
        """Create heatmap cells for temporal data."""
        error_types = sorted(
            {
                error_type
                for time_errors in temporal_counts.values()
                for error_type in time_errors.keys()
            }
        )

        cells = []
        for time_label in time_labels:
            for error_type in error_types:
                count = temporal_counts[time_label].get(error_type, 0)
                if count > 0:
                    cell = self._create_temporal_cell(
                        time_label, error_type, count, max_value
                    )
                    cells.append(cell)

        return cells, error_types

    def _create_temporal_cell(
        self, time_label: str, error_type: str, count: float, max_value: float
    ) -> HeatMapCell:
        """Create a single temporal heatmap cell."""
        intensity: float = count / max_value if max_value > 0 else 0.0
        severity = self._get_severity_for_type(error_type)

        return HeatMapCell(
            x=time_label,
            y=error_type,
            value=count,
            color_intensity=intensity,
            tooltip_data={
                "time": time_label,
                "error_type": error_type,
                "count": count,
                "severity": severity,
            },
            severity=severity,
        )

    def generate_function_error_heatmap(self) -> HeatMapData:
        """Generate heat map showing errors by function."""
        function_error_counts, max_value = self._count_errors_by_function()
        cells, functions, error_types = self._create_function_heatmap_cells(
            function_error_counts, max_value
        )

        return HeatMapData(
            cells=cells,
            x_labels=functions,
            y_labels=error_types,
            title="Error Distribution by Function",
            subtitle=f"Showing errors across {len(functions)} functions",
            max_value=max_value,
            min_value=0.0,
        )

    def _count_errors_by_function(
        self,
    ) -> tuple[defaultdict[str, defaultdict[str, float]], float]:
        """Count errors by function and type."""

        def _make_float_defaultdict_function() -> defaultdict[str, float]:
            return defaultdict(float)

        function_error_counts: defaultdict[str, defaultdict[str, float]] = defaultdict(
            _make_float_defaultdict_function
        )
        max_value = 0.0

        for pattern in self.error_patterns:
            if pattern.function_name:
                file_path = self._get_relative_path(pattern.file_path)
                function_id = f"{file_path}::{pattern.function_name}"
                error_type = pattern.error_type
                count = pattern.count

                function_error_counts[function_id][error_type] += count
                max_value = max(
                    max_value, function_error_counts[function_id][error_type]
                )

        return function_error_counts, max_value

    def _create_function_heatmap_cells(
        self,
        function_error_counts: defaultdict[str, defaultdict[str, float]],
        max_value: float,
    ) -> tuple[list[HeatMapCell], list[str], list[str]]:
        """Create heatmap cells for function error data."""
        functions = sorted(function_error_counts.keys())
        error_types = sorted(
            {
                error_type
                for func_errors in function_error_counts.values()
                for error_type in func_errors.keys()
            }
        )

        cells = []
        for function_id in functions:
            for error_type in error_types:
                count = function_error_counts[function_id].get(error_type, 0)
                if count > 0:
                    cell = self._create_function_cell(
                        function_id, error_type, count, max_value
                    )
                    cells.append(cell)

        return cells, functions, error_types

    def _create_function_cell(
        self, function_id: str, error_type: str, count: float, max_value: float
    ) -> HeatMapCell:
        """Create a single function heatmap cell."""
        intensity: float = count / max_value if max_value > 0 else 0.0
        severity = self._get_severity_for_type(error_type)

        return HeatMapCell(
            x=function_id,
            y=error_type,
            value=count,
            color_intensity=intensity,
            tooltip_data={
                "function": function_id,
                "error_type": error_type,
                "count": count,
                "severity": severity,
            },
            severity=severity,
        )

    def _analyze_test_failures(self) -> list[dict[str, t.Any]]:
        """Analyze test failure patterns."""
        errors: list[dict[str, t.Any]] = []

        # Look for pytest cache and reports
        pytest_cache = self.project_root / ".pytest_cache"
        if pytest_cache.exists():
            # Simulate some test failure patterns
            errors.extend(
                [
                    {
                        "type": "test_failure",
                        "message": "AssertionError: Expected 5 but got 3",
                        "file": "tests/test_calculator.py",
                        "function": "test_addition",
                        "line": 42,
                        "timestamp": datetime.now() - timedelta(days=2),
                    },
                    {
                        "type": "import_error",
                        "message": "ModuleNotFoundError: No module named 'missing_dep'",
                        "file": "tests/test_integration.py",
                        "function": "test_integration_flow",
                        "line": 15,
                        "timestamp": datetime.now() - timedelta(days=5),
                    },
                ]
            )

        return errors

    def _analyze_lint_errors(self) -> list[dict[str, t.Any]]:
        """Analyze linting error patterns."""
        errors: list[dict[str, t.Any]] = []

        # Look for ruff/flake8 outputs
        # Simulate common linting errors
        errors.extend(
            [
                {
                    "type": "unused_import",
                    "message": "F401 'os' imported but unused",
                    "file": "crackerjack/services/file_service.py",
                    "function": None,
                    "line": 3,
                    "timestamp": datetime.now() - timedelta(days=1),
                },
                {
                    "type": "line_too_long",
                    "message": "E501 line too long (89 > 88 characters)",
                    "file": "crackerjack/cli/options.py",
                    "function": "parse_arguments",
                    "line": 156,
                    "timestamp": datetime.now() - timedelta(hours=6),
                },
                {
                    "type": "complexity_error",
                    "message": "C901 'process_workflow' is too complex (16)",
                    "file": "crackerjack/orchestrators/workflow.py",
                    "function": "process_workflow",
                    "line": 89,
                    "timestamp": datetime.now() - timedelta(days=3),
                },
            ]
        )

        return errors

    def _analyze_git_history(self) -> list[dict[str, t.Any]]:
        """Analyze git commit history for error patterns."""
        errors: list[dict[str, t.Any]] = []

        # Look for fix commits and reverts
        # This would normally parse git log
        errors.extend(
            [
                {
                    "type": "hotfix",
                    "message": "Fix critical security vulnerability in auth",
                    "file": "crackerjack/services/security.py",
                    "function": "validate_token",
                    "line": None,
                    "timestamp": datetime.now() - timedelta(days=7),
                },
                {
                    "type": "revert",
                    "message": "Revert broken deployment pipeline",
                    "file": "crackerjack/cli/deploy.py",
                    "function": "deploy_application",
                    "line": None,
                    "timestamp": datetime.now() - timedelta(days=4),
                },
            ]
        )

        return errors

    def _analyze_log_files(self) -> list[dict[str, t.Any]]:
        """Analyze application log files for error patterns."""
        errors: list[dict[str, t.Any]] = []

        # Look for log files with error patterns
        log_dirs = [self.project_root / "logs", Path.home() / "logs"]

        for log_dir in log_dirs:
            if log_dir.exists():
                # Simulate log analysis
                errors.extend(
                    [
                        {
                            "type": "runtime_error",
                            "message": "ConnectionError: Failed to connect to database",
                            "file": "crackerjack/services/database.py",
                            "function": "connect",
                            "line": 78,
                            "timestamp": datetime.now() - timedelta(hours=12),
                        },
                        {
                            "type": "timeout_error",
                            "message": "TimeoutError: Request took longer than 30s",
                            "file": "crackerjack/services/http_client.py",
                            "function": "make_request",
                            "line": 124,
                            "timestamp": datetime.now() - timedelta(hours=18),
                        },
                    ]
                )

        return errors

    def _group_similar_errors(
        self, errors: list[dict[str, t.Any]]
    ) -> dict[str, list[dict[str, t.Any]]]:
        """Group similar errors together."""
        groups = defaultdict(list)

        for error in errors:
            # Create a key based on error type and file
            key = f"{error['type']}:{error['file']}"
            if error.get("function"):
                key += f":{error['function']}"

            groups[key].append(error)

        return dict[str, t.Any](groups)

    def _create_error_patterns(
        self, groups: dict[str, list[dict[str, t.Any]]], min_occurrences: int
    ) -> list[ErrorPattern]:
        """Create ErrorPattern objects from grouped errors."""
        patterns = []

        for group_key, error_list in groups.items():
            if len(error_list) < min_occurrences:
                continue

            first_error = error_list[0]
            timestamps = [e["timestamp"] for e in error_list]

            pattern = ErrorPattern(
                error_type=first_error["type"],
                message=first_error["message"],
                file_path=first_error["file"],
                function_name=first_error.get("function"),
                line_number=first_error.get("line"),
                count=len(error_list),
                severity="medium",  # Will be calculated later
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                trend="stable",  # Will be calculated later
                confidence=min(1.0, len(error_list) / 10.0),
                metadata={
                    "group_key": group_key,
                    "unique_messages": len({e["message"] for e in error_list}),
                },
            )

            patterns.append(pattern)

        return patterns

    def _calculate_error_trends(self) -> None:
        """Calculate trend information for error patterns."""
        for pattern in self.error_patterns:
            # Simple trend calculation based on recency
            time_diff = (datetime.now() - pattern.last_seen).days

            if time_diff <= 1:
                pattern.trend = "increasing"
            elif time_diff <= 7:
                pattern.trend = "stable"
            else:
                pattern.trend = "decreasing"

    def _assign_severity_levels(self) -> None:
        """Assign severity levels based on error type and frequency."""
        severity_map = {
            "security_vulnerability": "critical",
            "runtime_error": "high",
            "test_failure": "high",
            "import_error": "high",
            "complexity_error": "medium",
            "hotfix": "high",
            "revert": "medium",
            "timeout_error": "medium",
            "line_too_long": "low",
            "unused_import": "low",
        }

        for pattern in self.error_patterns:
            # Base severity from type
            base_severity = severity_map.get(pattern.error_type, "medium")

            # Increase severity for high-frequency errors
            if pattern.count > 10:
                severity_levels = ["low", "medium", "high", "critical"]
                current_index = severity_levels.index(base_severity)
                if current_index < len(severity_levels) - 1:
                    base_severity = severity_levels[current_index + 1]

            pattern.severity = base_severity

    def _get_relative_path(self, file_path: str) -> str:
        """Get relative path from project root."""
        try:
            path = Path(file_path)
            if path.is_absolute():
                return str(path.relative_to(self.project_root))
            return file_path
        except ValueError:
            return file_path

    def _get_severity_for_type(self, error_type: str) -> str:
        """Get severity level for error type."""
        for pattern in self.error_patterns:
            if pattern.error_type == error_type:
                return pattern.severity
        return "medium"


def analyze_error_patterns(
    project_root: str | Path, days: int = 30
) -> list[ErrorPattern]:
    """Analyze error patterns and return pattern data."""
    analyzer = ErrorPatternAnalyzer(Path(project_root))
    return analyzer.analyze_error_patterns(days=days)


def export_heatmap_data(heatmap: HeatMapData, output_path: str | Path) -> None:
    """Export heat map data to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(heatmap.to_dict(), f, indent=2)
