"""Heat map visualization generator for error patterns and code quality metrics."""

import json
import logging
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HeatMapCell:
    """Individual cell in a heat map."""

    x: int
    y: int
    value: float
    label: str
    metadata: dict[str, t.Any] = field(default_factory=dict)
    color_intensity: float = 0.0  # 0.0 to 1.0


@dataclass
class HeatMapData:
    """Complete heat map data structure."""

    title: str
    cells: list[HeatMapCell]
    x_labels: list[str]
    y_labels: list[str]
    color_scale: dict[str, t.Any]
    metadata: dict[str, t.Any] = field(default_factory=dict)
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

    def __init__(self):
        """Initialize heat map generator."""
        self.error_data: dict[str, list[dict]] = defaultdict(list)
        self.metric_data: dict[str, dict] = {}

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

        # Define time buckets based on granularity
        if granularity == "hourly":
            bucket_count = int(time_window.total_seconds() / 3600)
            bucket_size = timedelta(hours=1)
            x_label_format = "%H:%M"
        elif granularity == "daily":
            bucket_count = time_window.days
            bucket_size = timedelta(days=1)
            x_label_format = "%m/%d"
        else:  # weekly
            bucket_count = max(1, time_window.days // 7)
            bucket_size = timedelta(weeks=1)
            x_label_format = "Week %W"

        # Get unique file paths
        file_paths = list(self.error_data.keys())

        # Create time buckets
        time_buckets = []
        current_time = start_time
        for _ in range(bucket_count):
            time_buckets.append(current_time)
            current_time += bucket_size

        # Count errors in each bucket for each file
        error_matrix = defaultdict(lambda: defaultdict(int))

        for file_path, errors in self.error_data.items():
            for error in errors:
                error_time = error["timestamp"]
                if start_time <= error_time <= now:
                    # Find appropriate time bucket
                    bucket_index = min(
                        len(time_buckets) - 1,
                        int(
                            (error_time - start_time).total_seconds()
                            / bucket_size.total_seconds()
                        ),
                    )
                    error_matrix[file_path][bucket_index] += 1

        # Create heat map cells
        cells = []
        max_errors = (
            max(
                max(bucket_counts.values()) if bucket_counts else 0
                for bucket_counts in error_matrix.values()
            )
            or 1
        )

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

        # Create labels
        x_labels = [bucket.strftime(x_label_format) for bucket in time_buckets]
        y_labels = [Path(fp).name for fp in file_paths]

        return HeatMapData(
            title=f"Error Frequency Heat Map ({granularity.title()})",
            cells=cells,
            x_labels=x_labels,
            y_labels=y_labels,
            color_scale=self.color_schemes["error_intensity"],
            metadata={
                "granularity": granularity,
                "time_window_days": time_window.days,
                "max_errors": max_errors,
                "total_files": len(file_paths),
            },
        )

    def generate_code_complexity_heatmap(self, project_root: str | Path) -> HeatMapData:
        """Generate heat map showing code complexity across files and functions."""
        from .dependency_analyzer import analyze_project_dependencies

        # Analyze project to get complexity data
        project_root = Path(project_root)
        dependency_graph = analyze_project_dependencies(project_root)

        # Group nodes by file and extract complexity
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

        # Create heat map data
        cells = []
        files = list(file_complexity.keys())
        max_complexity = (
            max(
                max(item["complexity"] for item in items)
                for items in file_complexity.values()
                if items
            )
            or 1
        )

        for y, file_path in enumerate(files):
            functions = sorted(file_complexity[file_path], key=lambda x: x["line"])

            for x, func_data in enumerate(functions[:50]):  # Limit to 50 functions
                complexity = func_data["complexity"]
                intensity = min(
                    1.0, complexity / 15
                )  # Normalize to complexity threshold

                # Determine complexity category
                if complexity <= 5:
                    complexity_level = "simple"
                elif complexity <= 10:
                    complexity_level = "moderate"
                elif complexity <= 15:
                    complexity_level = "complex"
                elif complexity <= 20:
                    complexity_level = "very_complex"
                else:
                    complexity_level = "extremely_complex"

                cell = HeatMapCell(
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
                cells.append(cell)

        # Create labels (show only first 20 characters of function names)
        x_labels = []
        y_labels = [Path(fp).name for fp in files]

        # Get unique x positions for labeling
        max_x = max(cell.x for cell in cells) if cells else 0
        for x in range(max_x + 1):
            x_labels.append(f"Func {x + 1}")

        return HeatMapData(
            title="Code Complexity Heat Map",
            cells=cells,
            x_labels=x_labels,
            y_labels=y_labels,
            color_scale=self.color_schemes["complexity"],
            metadata={
                "max_complexity": max_complexity,
                "total_files": len(files),
                "complexity_threshold": 15,
            },
        )

    def generate_quality_metrics_heatmap(self) -> HeatMapData:
        """Generate heat map showing various quality metrics."""
        if not self.metric_data:
            return HeatMapData(
                title="Quality Metrics Heat Map",
                cells=[],
                x_labels=[],
                y_labels=[],
                color_scale=self.color_schemes["quality_score"],
            )

        # Define metric types to visualize
        metric_types = [
            "test_coverage",
            "complexity_score",
            "duplication_ratio",
            "documentation_ratio",
            "security_score",
            "performance_score",
        ]

        # Create cells
        cells = []
        identifiers = list(self.metric_data.keys())

        # Calculate max values for normalization
        max_values = {}
        for metric_type in metric_types:
            values = []
            for data in self.metric_data.values():
                if metric_type in data["metrics"]:
                    values.append(data["metrics"][metric_type])
            max_values[metric_type] = max(values) if values else 1

        for y, identifier in enumerate(identifiers):
            data = self.metric_data[identifier]
            metrics = data["metrics"]

            for x, metric_type in enumerate(metric_types):
                value = metrics.get(metric_type, 0)
                intensity = value / max_values[metric_type]

                # Convert to quality score (higher is better for most metrics)
                if metric_type in ("complexity_score", "duplication_ratio"):
                    # Lower is better for these metrics
                    quality_score = 1.0 - min(1.0, intensity)
                else:
                    # Higher is better
                    quality_score = intensity

                # Determine quality level
                if quality_score >= 0.9:
                    quality_level = "excellent"
                elif quality_score >= 0.7:
                    quality_level = "good"
                elif quality_score >= 0.5:
                    quality_level = "average"
                elif quality_score >= 0.3:
                    quality_level = "poor"
                else:
                    quality_level = "critical"

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

    def generate_test_failure_heatmap(
        self, time_window: timedelta = timedelta(days=14)
    ) -> HeatMapData:
        """Generate heat map showing test failure patterns."""
        # Filter for test-related errors
        test_errors = []
        now = datetime.now()
        start_time = now - time_window

        for file_path, errors in self.error_data.items():
            for error in errors:
                if error["timestamp"] >= start_time and (
                    "test" in error["error_type"].lower() or "test" in file_path.lower()
                ):
                    test_errors.append(
                        {
                            **error,
                            "file_path": file_path,
                        }
                    )

        # Group by test file and error type
        test_matrix = defaultdict(lambda: defaultdict(int))

        for error in test_errors:
            file_name = Path(error["file_path"]).name
            error_type = error["error_type"]
            test_matrix[file_name][error_type] += 1

        # Create cells
        cells = []
        test_files = list(test_matrix.keys())
        all_error_types = set()

        for error_types in test_matrix.values():
            all_error_types.update(error_types.keys())

        error_types = list(all_error_types)

        # Calculate max failures for normalization
        max_failures = (
            max(
                max(error_counts.values()) if error_counts else 0
                for error_counts in test_matrix.values()
            )
            or 1
        )

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

        return HeatMapData(
            title="Test Failure Heat Map",
            cells=cells,
            x_labels=error_types,
            y_labels=test_files,
            color_scale=self.color_schemes["error_intensity"],
            metadata={
                "time_window_days": time_window.days,
                "max_failures": max_failures,
                "total_test_files": len(test_files),
                "total_error_types": len(error_types),
            },
        )

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
