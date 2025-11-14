"""Heat map visualization generator for error patterns and code quality metrics."""

import json
import logging
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .dependency_analyzer import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class HeatMapCell:
    """Individual cell in a heat map."""

    x: int
    y: int
    value: float
    label: str
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    color_intensity: float = 0.0  # 0.0 to 1.0


@dataclass
class HeatMapData:
    """Complete heat map data structure."""

    title: str
    cells: list[HeatMapCell]
    x_labels: list[str]
    y_labels: list[str]
    color_scale: dict[str, t.Any]
    metadata: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "cells": [
                {
                    "x": cell.x,
                    "y": cell.y,
                    "value": cell.value,
                    "label": cell.label,
                    "color_intensity": cell.color_intensity,
                    "metadata": cell.metadata,
                }
                for cell in self.cells
            ],
            "x_labels": self.x_labels,
            "y_labels": self.y_labels,
            "color_scale": self.color_scale,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
        }


class HeatMapGenerator:
    """Generates heat map visualizations for various code quality metrics."""

    def __init__(self) -> None:
        """Initialize heat map generator."""
        self.error_data: dict[str, list[dict[str, t.Any]]] = defaultdict(list)
        self.metric_data: dict[str, dict[str, t.Any]] = {}

        # Color schemes
        self.color_schemes = {
            "error_intensity": {
                "low": "#90EE90",  # Light green
                "medium": "#FFD700",  # Gold
                "high": "#FF6347",  # Tomato
                "critical": "#DC143C",  # Crimson
            },
            "quality_score": {
                "excellent": "#228B22",  # Forest green
                "good": "#32CD32",  # Lime green
                "average": "#FFD700",  # Gold
                "poor": "#FF6347",  # Tomato
                "critical": "#DC143C",  # Crimson
            },
            "complexity": {
                "simple": "#E6F3FF",  # Very light blue
                "moderate": "#B3D9FF",  # Light blue
                "complex": "#80BFFF",  # Medium blue
                "very_complex": "#4D9FFF",  # Dark blue
                "extremely_complex": "#1A5CFF",  # Very dark blue
            },
        }

    def add_error_data(
        self,
        file_path: str,
        line_number: int,
        error_type: str,
        severity: str,
        timestamp: datetime | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Add error data for heat map generation."""
        if timestamp is None:
            timestamp = datetime.now()

        error_record = {
            "file_path": file_path,
            "line_number": line_number,
            "error_type": error_type,
            "severity": severity,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        self.error_data[file_path].append(error_record)

    def add_metric_data(
        self,
        identifier: str,
        metrics: dict[str, float],
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Add metric data for heat map generation."""
        self.metric_data[identifier] = {
            "metrics": metrics,
            "metadata": metadata or {},
            "timestamp": datetime.now(),
        }

    def generate_error_frequency_heatmap(
        self,
        time_window: timedelta = timedelta(days=7),
        granularity: str = "hourly",  # hourly, daily, weekly
    ) -> HeatMapData:
        """Generate heat map showing error frequency patterns over time."""
        now = datetime.now()
        start_time = now - time_window

        bucket_config = self._get_time_bucket_config(time_window, granularity)
        file_paths = list[t.Any](self.error_data.keys())
        time_buckets = self._create_time_buckets(start_time, bucket_config)
        error_matrix = self._build_error_matrix(
            start_time, now, time_buckets, bucket_config
        )
        cells = self._create_frequency_cells(file_paths, time_buckets, error_matrix)
        labels = self._create_frequency_labels(
            file_paths, time_buckets, bucket_config["format"]
        )

        return HeatMapData(
            title=f"Error Frequency Heat Map ({granularity.title()})",
            cells=cells,
            x_labels=labels[0],
            y_labels=labels[1],
            color_scale=self.color_schemes["error_intensity"],
            metadata={
                "granularity": granularity,
                "time_window_days": time_window.days,
                "max_errors": self._calculate_max_errors(error_matrix),
                "total_files": len(file_paths),
            },
        )

    def _get_time_bucket_config(
        self, time_window: timedelta, granularity: str
    ) -> dict[str, t.Any]:
        """Get time bucket configuration based on granularity."""
        if granularity == "hourly":
            return {
                "count": int(time_window.total_seconds() / 3600),
                "size": timedelta(hours=1),
                "format": "%H:%M",
            }
        elif granularity == "daily":
            return {
                "count": time_window.days,
                "size": timedelta(days=1),
                "format": "%m/%d",
            }
        # weekly
        return {
            "count": max(1, time_window.days // 7),
            "size": timedelta(weeks=1),
            "format": "Week %W",
        }

    def _create_time_buckets(
        self, start_time: datetime, bucket_config: dict[str, t.Any]
    ) -> list[datetime]:
        """Create time buckets for the heatmap."""
        time_buckets = []
        current_time = start_time
        for _ in range(bucket_config["count"]):
            time_buckets.append(current_time)
            current_time += bucket_config["size"]
        return time_buckets

    def _build_error_matrix(
        self,
        start_time: datetime,
        end_time: datetime,
        time_buckets: list[datetime],
        bucket_config: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        """Build error count matrix for files and time buckets."""
        from collections import defaultdict

        error_matrix: dict[str, t.Any] = defaultdict(
            lambda: defaultdict(int)  # type: ignore[call-overload]
        )

        for file_path, errors in self.error_data.items():
            for error in errors:
                error_time = error["timestamp"]
                if start_time <= error_time <= end_time:
                    bucket_index = self._find_time_bucket_index(
                        error_time, start_time, time_buckets, bucket_config["size"]
                    )
                    error_matrix[file_path][bucket_index] += 1

        return error_matrix

    def _find_time_bucket_index(
        self,
        error_time: datetime,
        start_time: datetime,
        time_buckets: list[datetime],
        bucket_size: timedelta,
    ) -> int:
        """Find the appropriate time bucket index for an error."""
        return min(
            len(time_buckets) - 1,
            int(
                (error_time - start_time).total_seconds() / bucket_size.total_seconds()
            ),
        )

    def _create_frequency_cells(
        self,
        file_paths: list[str],
        time_buckets: list[datetime],
        error_matrix: dict[str, t.Any],
    ) -> list[HeatMapCell]:
        """Create heat map cells from error frequency data."""
        cells = []
        max_errors = self._calculate_max_errors(error_matrix)

        for y, file_path in enumerate(file_paths):
            for x in range(len(time_buckets)):
                error_count = error_matrix[file_path][x]
                intensity = error_count / max_errors

                cell = HeatMapCell(
                    x=x,
                    y=y,
                    value=error_count,
                    label=f"{Path(file_path).name}: {error_count} errors",
                    color_intensity=intensity,
                    metadata={
                        "file_path": file_path,
                        "time_bucket": time_buckets[x].isoformat(),
                        "error_count": error_count,
                    },
                )
                cells.append(cell)

        return cells

    def _create_frequency_labels(
        self, file_paths: list[str], time_buckets: list[datetime], x_label_format: str
    ) -> tuple[list[str], list[str]]:
        """Create x and y labels for frequency heatmap."""
        x_labels = [bucket.strftime(x_label_format) for bucket in time_buckets]
        y_labels = [Path(fp).name for fp in file_paths]
        return x_labels, y_labels

    def _calculate_max_errors(self, error_matrix: dict[str, t.Any]) -> int:
        """Calculate maximum error count for normalization."""
        return (
            max(
                max(bucket_counts.values()) if bucket_counts else 0
                for bucket_counts in error_matrix.values()
            )
            or 1
        )

    def generate_code_complexity_heatmap(self, project_root: str | Path) -> HeatMapData:
        """Generate heat map showing code complexity across files and functions."""
        from .dependency_analyzer import analyze_project_dependencies

        project_root = Path(project_root)
        dependency_graph = analyze_project_dependencies(project_root)

        file_complexity = self._extract_file_complexity_data(
            dependency_graph, project_root
        )
        cells = self._create_complexity_cells(file_complexity)
        x_labels, y_labels = self._create_complexity_labels(file_complexity, cells)
        max_complexity = self._calculate_max_complexity(file_complexity)

        return HeatMapData(
            title="Code Complexity Heat Map",
            cells=cells,
            x_labels=x_labels,
            y_labels=y_labels,
            color_scale=self.color_schemes["complexity"],
            metadata={
                "max_complexity": max_complexity,
                "total_files": len(file_complexity),
                "complexity_threshold": 15,
            },
        )

    def _extract_file_complexity_data(
        self, dependency_graph: DependencyGraph, project_root: Path
    ) -> dict[str, t.Any]:
        """Extract complexity data grouped by file."""
        file_complexity = defaultdict(list)

        for node in dependency_graph.nodes.values():
            if node.type in ("function", "method", "class"):
                relative_path = str(Path(node.file_path).relative_to(project_root))
                file_complexity[relative_path].append(
                    {
                        "name": node.name,
                        "complexity": node.complexity,
                        "type": node.type,
                        "line": node.line_number,
                    }
                )
        return file_complexity

    def _create_complexity_cells(
        self, file_complexity: dict[str, t.Any]
    ) -> list[HeatMapCell]:
        """Create heat map cells from complexity data."""
        cells = []
        files = list[t.Any](file_complexity.keys())

        for y, file_path in enumerate(files):
            from operator import itemgetter

            functions = sorted(file_complexity[file_path], key=itemgetter("line"))

            for x, func_data in enumerate(functions[:50]):  # Limit to 50 functions
                cell = self._create_complexity_cell(x, y, func_data, file_path)
                cells.append(cell)

        return cells

    def _create_complexity_cell(
        self, x: int, y: int, func_data: dict[str, t.Any], file_path: str
    ) -> HeatMapCell:
        """Create a single complexity heat map cell."""
        complexity = func_data["complexity"]
        intensity = min(1.0, complexity / 15)  # Normalize to complexity threshold
        complexity_level = self._get_complexity_level(complexity)

        return HeatMapCell(
            x=x,
            y=y,
            value=complexity,
            label=f"{func_data['name']}: {complexity}",
            color_intensity=intensity,
            metadata={
                "file_path": file_path,
                "function_name": func_data["name"],
                "function_type": func_data["type"],
                "line_number": func_data["line"],
                "complexity": complexity,
                "complexity_level": complexity_level,
            },
        )

    def _get_complexity_level(self, complexity: int) -> str:
        """Determine complexity category based on value."""
        if complexity <= 5:
            return "simple"
        elif complexity <= 10:
            return "moderate"
        elif complexity <= 15:
            return "complex"
        elif complexity <= 20:
            return "very_complex"
        return "extremely_complex"

    def _create_complexity_labels(
        self, file_complexity: dict[str, t.Any], cells: list[HeatMapCell]
    ) -> tuple[list[str], list[str]]:
        """Create x and y labels for complexity heat map."""
        files = list[t.Any](file_complexity.keys())
        y_labels = [Path(fp).name for fp in files]

        max_x = max(cell.x for cell in cells) if cells else 0
        x_labels = [f"Func {x + 1}" for x in range(max_x + 1)]

        return x_labels, y_labels

    def _calculate_max_complexity(self, file_complexity: dict[str, t.Any]) -> int:
        """Calculate maximum complexity value across all functions."""
        return (
            max(
                max(item["complexity"] for item in items)
                for items in file_complexity.values()
                if items
            )
            or 1
        )

    def generate_quality_metrics_heatmap(self) -> HeatMapData:
        """Generate heat map showing various quality metrics."""
        if not self.metric_data:
            return self._get_default_quality_heatmap()

        metric_types = self._get_quality_metric_types()
        identifiers = list[t.Any](self.metric_data.keys())
        max_values = self._calculate_metric_max_values(metric_types)
        cells = self._create_quality_metric_cells(identifiers, metric_types, max_values)

        return HeatMapData(
            title="Quality Metrics Heat Map",
            cells=cells,
            x_labels=metric_types,
            y_labels=identifiers,
            color_scale=self.color_schemes["quality_score"],
            metadata={
                "metric_count": len(metric_types),
                "entity_count": len(identifiers),
            },
        )

    def _get_default_quality_heatmap(self) -> HeatMapData:
        """Return default quality heatmap for empty data."""
        return HeatMapData(
            title="Quality Metrics Heat Map",
            cells=[],
            x_labels=[],
            y_labels=[],
            color_scale=self.color_schemes["quality_score"],
        )

    def _get_quality_metric_types(self) -> list[str]:
        """Define metric types to visualize."""
        return [
            "test_coverage",
            "complexity_score",
            "duplication_ratio",
            "documentation_ratio",
            "security_score",
            "performance_score",
        ]

    def _calculate_metric_max_values(self, metric_types: list[str]) -> dict[str, float]:
        """Calculate max values for normalization."""
        max_values: dict[str, float] = {}
        for metric_type in metric_types:
            values = [
                data["metrics"][metric_type]
                for data in self.metric_data.values()
                if metric_type in data["metrics"]
            ]
            max_values[metric_type] = max(values) if values else 1
        return max_values

    def _create_quality_metric_cells(
        self,
        identifiers: list[str],
        metric_types: list[str],
        max_values: dict[str, float],
    ) -> list[HeatMapCell]:
        """Create cells for quality metrics heatmap."""
        cells = []
        for y, identifier in enumerate(identifiers):
            data = self.metric_data[identifier]
            metrics = data["metrics"]

            for x, metric_type in enumerate(metric_types):
                value = metrics.get(metric_type, 0)
                intensity = value / max_values[metric_type]
                quality_score = self._calculate_quality_score(metric_type, intensity)
                quality_level = self._determine_quality_level(quality_score)

                cell = HeatMapCell(
                    x=x,
                    y=y,
                    value=value,
                    label=f"{identifier}: {metric_type} = {value:.2f}",
                    color_intensity=quality_score,
                    metadata={
                        "identifier": identifier,
                        "metric_type": metric_type,
                        "raw_value": value,
                        "quality_score": quality_score,
                        "quality_level": quality_level,
                    },
                )
                cells.append(cell)
        return cells

    def _calculate_quality_score(self, metric_type: str, intensity: float) -> float:
        """Calculate quality score for a metric (higher is better for most metrics)."""
        if metric_type in ("complexity_score", "duplication_ratio"):
            # Lower is better for these metrics
            return 1.0 - min(1.0, intensity)
        # Higher is better
        return intensity

    def _determine_quality_level(self, quality_score: float) -> str:
        """Determine quality level from quality score."""
        if quality_score >= 0.9:
            return "excellent"
        elif quality_score >= 0.7:
            return "good"
        elif quality_score >= 0.5:
            return "average"
        elif quality_score >= 0.3:
            return "poor"
        return "critical"

    def generate_test_failure_heatmap(
        self, time_window: timedelta = timedelta(days=14)
    ) -> HeatMapData:
        """Generate heat map showing test failure patterns."""
        test_errors = self._filter_test_errors(time_window)
        test_matrix = self._group_test_errors_by_matrix(test_errors)
        test_files = list[t.Any](test_matrix.keys())
        error_types = self._collect_error_types(test_matrix)
        max_failures = self._calculate_max_test_failures(test_matrix)
        cells = self._create_test_failure_cells(
            test_matrix, test_files, error_types, max_failures
        )
        metadata = self._build_test_failure_metadata(
            time_window, max_failures, test_files, error_types
        )

        return HeatMapData(
            title="Test Failure Heat Map",
            cells=cells,
            x_labels=error_types,
            y_labels=test_files,
            color_scale=self.color_schemes["error_intensity"],
            metadata=metadata,
        )

    def _filter_test_errors(self, time_window: timedelta) -> list[dict[str, t.Any]]:
        """Filter for test-related errors within the time window."""
        test_errors: list[dict[str, t.Any]] = []
        now = datetime.now()
        start_time = now - time_window

        for file_path, errors in self.error_data.items():
            for error in errors:
                if error["timestamp"] >= start_time and (
                    "test" in error["error_type"].lower() or "test" in file_path.lower()
                ):
                    test_errors.append(error | {"file_path": file_path})
        return test_errors

    def _group_test_errors_by_matrix(
        self, test_errors: list[dict[str, t.Any]]
    ) -> defaultdict[str, defaultdict[str, int]]:
        """Group test errors by file and error type."""
        from collections import defaultdict as dd

        def make_inner_defaultdict() -> defaultdict[str, int]:
            return dd(int)

        test_matrix: defaultdict[str, defaultdict[str, int]] = defaultdict(
            make_inner_defaultdict
        )

        for error in test_errors:
            file_name = Path(error["file_path"]).name
            error_type = error["error_type"]
            test_matrix[file_name][error_type] += 1

        return test_matrix

    def _collect_error_types(
        self, test_matrix: defaultdict[str, defaultdict[str, int]]
    ) -> list[str]:
        """Collect all unique error types from the test matrix."""
        all_error_types: set[str] = set()
        for error_types in test_matrix.values():
            all_error_types.update(error_types.keys())
        return list[t.Any](all_error_types)

    def _calculate_max_test_failures(
        self, test_matrix: defaultdict[str, defaultdict[str, int]]
    ) -> int:
        """Calculate maximum failures for normalization."""
        return (
            max(
                max(error_counts.values()) if error_counts else 0
                for error_counts in test_matrix.values()
            )
            or 1
        )

    def _create_test_failure_cells(
        self,
        test_matrix: defaultdict[str, defaultdict[str, int]],
        test_files: list[str],
        error_types: list[str],
        max_failures: int,
    ) -> list[HeatMapCell]:
        """Create cells for the test failure heatmap."""
        cells = []
        for y, test_file in enumerate(test_files):
            for x, error_type in enumerate(error_types):
                failure_count = test_matrix[test_file][error_type]
                intensity = failure_count / max_failures

                cell = HeatMapCell(
                    x=x,
                    y=y,
                    value=failure_count,
                    label=f"{test_file}: {error_type} ({failure_count} failures)",
                    color_intensity=intensity,
                    metadata={
                        "test_file": test_file,
                        "error_type": error_type,
                        "failure_count": failure_count,
                    },
                )
                cells.append(cell)
        return cells

    def _build_test_failure_metadata(
        self,
        time_window: timedelta,
        max_failures: int,
        test_files: list[str],
        error_types: list[str],
    ) -> dict[str, t.Any]:
        """Build metadata dictionary for test failure heatmap."""
        return {
            "time_window_days": time_window.days,
            "max_failures": max_failures,
            "total_test_files": len(test_files),
            "total_error_types": len(error_types),
        }

    def export_heatmap_data(
        self, heatmap: HeatMapData, output_path: str | Path, format_type: str = "json"
    ) -> None:
        """Export heat map data to file."""
        if format_type.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(heatmap.to_dict(), f, indent=2)
        elif format_type.lower() == "csv":
            import csv

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(["x", "y", "value", "label", "intensity"])

                # Write data
                for cell in heatmap.cells:
                    writer.writerow(
                        [
                            cell.x,
                            cell.y,
                            cell.value,
                            cell.label,
                            cell.color_intensity,
                        ]
                    )
        else:
            msg = f"Unsupported format: {format_type}"
            raise ValueError(msg)

    def generate_html_visualization(self, heatmap: HeatMapData) -> str:
        """Generate HTML visualization for the heat map."""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .heatmap {{ display: grid; gap: 1px; background: #ddd; }}
        .cell {{
            padding: 5px;
            text-align: center;
            font-size: 10px;
            min-width: 80px;
            min-height: 20px;
        }}
        .legend {{ margin-top: 20px; }}
        .legend-item {{ display: inline-block; margin: 0 10px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="heatmap" style="grid-template-columns: repeat({cols}, 1fr);">
        {cells_html}
    </div>
    <div class="legend">
        {legend_html}
    </div>
    <p>Generated at: {generated_at}</p>
</body>
</html>
        """

        # Generate cells HTML
        cells_html = ""
        for cell in heatmap.cells:
            # Calculate color based on intensity
            intensity = int(255 * (1 - cell.color_intensity))
            color = f"rgb({255}, {intensity}, {intensity})"

            cells_html += f"""
                <div class="cell" style="background-color: {color};"
                     title="{cell.label}">
                    {cell.value:.1f}
                </div>
            """

        # Generate legend HTML
        legend_html = ""
        for level, color in heatmap.color_scale.items():
            legend_html += f"""
                <div class="legend-item">
                    <span style="background-color: {color}; padding: 2px 8px;">
                        {level.title()}
                    </span>
                </div>
            """

        max_x = max(cell.x for cell in heatmap.cells) if heatmap.cells else 1

        return html_template.format(
            title=heatmap.title,
            cols=max_x + 1,
            cells_html=cells_html,
            legend_html=legend_html,
            generated_at=heatmap.generated_at.isoformat(),
        )
