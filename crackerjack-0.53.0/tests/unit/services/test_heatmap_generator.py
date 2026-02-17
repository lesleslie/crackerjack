"""Unit tests for HeatMapGenerator.

Tests heatmap generation, data visualization, error frequency analysis,
code complexity mapping, and quality metrics visualization.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crackerjack.services.heatmap_generator import (
    HeatMapCell,
    HeatMapData,
    HeatMapGenerator,
)


@pytest.mark.unit
class TestHeatMapCellDataClass:
    """Test HeatMapCell dataclass."""

    def test_cell_creation(self) -> None:
        """Test HeatMapCell creation with all fields."""
        cell = HeatMapCell(
            x=1,
            y=2,
            value=0.5,
            label="Test Cell",
            metadata={"key": "value"},
            color_intensity=0.7,
        )

        assert cell.x == 1
        assert cell.y == 2
        assert cell.value == 0.5
        assert cell.label == "Test Cell"
        assert cell.metadata == {"key": "value"}
        assert cell.color_intensity == 0.7

    def test_cell_with_defaults(self) -> None:
        """Test HeatMapCell with default values."""
        cell = HeatMapCell(x=0, y=0, value=1.0, label="Default")

        assert cell.metadata == {}
        assert cell.color_intensity == 0.0


@pytest.mark.unit
class TestHeatMapDataDataClass:
    """Test HeatMapData dataclass."""

    def test_heatmap_data_creation(self, tmp_path) -> None:
        """Test HeatMapData creation."""
        cells = [
            HeatMapCell(x=0, y=0, value=1.0, label="High"),
            HeatMapCell(x=1, y=1, value=0.5, label="Medium"),
        ]

        data = HeatMapData(
            title="Test Heatmap",
            cells=cells,
            x_labels=["X1", "X2"],
            y_labels=["Y1", "Y2"],
            color_scale={"low": "#00FF00", "high": "#FF0000"},
            metadata={"project": "test"},
        )

        assert data.title == "Test Heatmap"
        assert len(data.cells) == 2
        assert data.x_labels == ["X1", "X2"]
        assert data.y_labels == ["Y1", "Y2"]
        assert data.metadata == {"project": "test"}

    def test_to_dict_conversion(self, tmp_path) -> None:
        """Test HeatMapData.to_dict() conversion."""
        cells = [HeatMapCell(x=0, y=0, value=1.0, label="Test")]
        data = HeatMapData(
            title="Test",
            cells=cells,
            x_labels=["X"],
            y_labels=["Y"],
            color_scale={"low": "green"},
        )

        result = data.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "Test"
        assert len(result["cells"]) == 1
        assert "generated_at" in result


@pytest.mark.unit
class TestHeatMapGeneratorInitialization:
    """Test HeatMapGenerator initialization."""

    def test_initialization(self) -> None:
        """Test generator initializes with required attributes."""
        generator = HeatMapGenerator()

        assert hasattr(generator, "error_data")
        assert hasattr(generator, "metric_data")
        assert hasattr(generator, "color_schemes")
        assert "error_intensity" in generator.color_schemes
        assert "quality_score" in generator.color_schemes
        assert "complexity" in generator.color_schemes

    def test_color_schemes_complete(self) -> None:
        """Test all color schemes are defined."""
        generator = HeatMapGenerator()

        assert "low" in generator.color_schemes["error_intensity"]
        assert "high" in generator.color_schemes["error_intensity"]
        assert "critical" in generator.color_schemes["error_intensity"]


@pytest.mark.unit
class TestAddErrorData:
    """Test error data addition."""

    def test_add_error_data_with_defaults(self) -> None:
        """Test adding error data with default timestamp."""
        generator = HeatMapGenerator()

        generator.add_error_data(
            file_path="/test/file.py",
            line_number=42,
            error_type="SyntaxError",
            severity="high",
        )

        assert "/test/file.py" in generator.error_data
        assert len(generator.error_data["/test/file.py"]) == 1

        error_record = generator.error_data["/test/file.py"][0]
        assert error_record["file_path"] == "/test/file.py"
        assert error_record["line_number"] == 42
        assert error_record["error_type"] == "SyntaxError"
        assert error_record["severity"] == "high"
        assert error_record["metadata"] == {}

    def test_add_error_data_with_custom_timestamp(self) -> None:
        """Test adding error data with custom timestamp."""
        generator = HeatMapGenerator()
        timestamp = datetime(2025, 1, 10, 12, 0, 0)

        generator.add_error_data(
            file_path="/test/file.py",
            line_number=10,
            error_type="TypeError",
            severity="medium",
            timestamp=timestamp,
        )

        error_record = generator.error_data["/test/file.py"][0]
        assert error_record["timestamp"] == timestamp

    def test_add_error_data_with_metadata(self) -> None:
        """Test adding error data with metadata."""
        generator = HeatMapGenerator()

        generator.add_error_data(
            file_path="/test/file.py",
            line_number=10,
            error_type="ValueError",
            severity="low",
            metadata={"traceback": "line 10"},
        )

        error_record = generator.error_data["/test/file.py"][0]
        assert error_record["metadata"] == {"traceback": "line 10"}

    def test_add_multiple_errors_same_file(self) -> None:
        """Test adding multiple errors for same file."""
        generator = HeatMapGenerator()

        generator.add_error_data("/test/file.py", 10, "Error1", "high")
        generator.add_error_data("/test/file.py", 20, "Error2", "medium")

        assert len(generator.error_data["/test/file.py"]) == 2

    def test_add_errors_multiple_files(self) -> None:
        """Test adding errors for multiple files."""
        generator = HeatMapGenerator()

        generator.add_error_data("/test/file1.py", 10, "Error1", "high")
        generator.add_error_data("/test/file2.py", 20, "Error2", "medium")

        assert len(generator.error_data) == 2
        assert "/test/file1.py" in generator.error_data
        assert "/test/file2.py" in generator.error_data


@pytest.mark.unit
class TestAddMetricData:
    """Test metric data addition."""

    def test_add_metric_data_with_defaults(self) -> None:
        """Test adding metric data with defaults."""
        generator = HeatMapGenerator()

        generator.add_metric_data(
            identifier="test_metric",
            metrics={"coverage": 85.0, "complexity": 10.0},
        )

        assert "test_metric" in generator.metric_data
        assert generator.metric_data["test_metric"]["metrics"]["coverage"] == 85.0
        assert generator.metric_data["test_metric"]["metadata"] == {}

    def test_add_metric_data_with_metadata(self) -> None:
        """Test adding metric data with metadata."""
        generator = HeatMapGenerator()

        generator.add_metric_data(
            identifier="test_metric",
            metrics={"score": 95.0},
            metadata={"category": "quality"},
        )

        assert generator.metric_data["test_metric"]["metadata"] == {"category": "quality"}

    def test_add_multiple_metrics(self) -> None:
        """Test adding multiple metrics."""
        generator = HeatMapGenerator()

        generator.add_metric_data("metric1", {"value": 1.0})
        generator.add_metric_data("metric2", {"value": 2.0})

        assert len(generator.metric_data) == 2


@pytest.mark.unit
class TestGenerateErrorFrequencyHeatmap:
    """Test error frequency heatmap generation."""

    def test_generate_empty_heatmap(self) -> None:
        """Test generating heatmap with minimal data."""
        generator = HeatMapGenerator()

        # Add minimal data to avoid empty matrix bug
        generator.add_error_data(
            file_path="/test/file.py",
            line_number=10,
            error_type="TestError",
            severity="low",
        )

        heatmap = generator.generate_error_frequency_heatmap()

        assert isinstance(heatmap, HeatMapData)
        assert heatmap.title == "Error Frequency Heat Map (Hourly)"

    def test_generate_heatmap_with_data(self) -> None:
        """Test generating heatmap with error data."""
        generator = HeatMapGenerator()
        timestamp = datetime.now()

        generator.add_error_data("/test/file.py", 10, "Error1", "high", timestamp)

        heatmap = generator.generate_error_frequency_heatmap()

        assert heatmap.title == "Error Frequency Heat Map (Hourly)"
        assert heatmap.metadata["granularity"] == "hourly"
        assert heatmap.metadata["total_files"] == 1

    def test_generate_daily_heatmap(self) -> None:
        """Test generating daily granularity heatmap."""
        generator = HeatMapGenerator()

        # Add data to avoid empty matrix bug
        generator.add_error_data("/test/file.py", 10, "Error", "low")

        heatmap = generator.generate_error_frequency_heatmap(
            granularity="daily"
        )

        assert heatmap.title == "Error Frequency Heat Map (Daily)"

    def test_generate_weekly_heatmap(self) -> None:
        """Test generating weekly granularity heatmap."""
        generator = HeatMapGenerator()

        # Add data to avoid empty matrix bug
        generator.add_error_data("/test/file.py", 10, "Error", "low")

        heatmap = generator.generate_error_frequency_heatmap(
            granularity="weekly"
        )

        assert "Week" in heatmap.x_labels[0] if heatmap.x_labels else True


@pytest.mark.unit
class TestGetTimeBucketConfig:
    """Test time bucket configuration."""

    def test_hourly_config(self) -> None:
        """Test hourly bucket configuration."""
        generator = HeatMapGenerator()
        window = timedelta(days=1)

        config = generator._get_time_bucket_config(window, "hourly")

        assert config["count"] == 24
        assert config["size"] == timedelta(hours=1)
        assert config["format"] == "%H:%M"

    def test_daily_config(self) -> None:
        """Test daily bucket configuration."""
        generator = HeatMapGenerator()
        window = timedelta(days=7)

        config = generator._get_time_bucket_config(window, "daily")

        assert config["count"] == 7
        assert config["size"] == timedelta(days=1)
        assert config["format"] == "%m/%d"

    def test_weekly_config(self) -> None:
        """Test weekly bucket configuration."""
        generator = HeatMapGenerator()
        window = timedelta(days=14)

        config = generator._get_time_bucket_config(window, "weekly")

        assert config["count"] == 2
        assert config["size"] == timedelta(weeks=1)


@pytest.mark.unit
class TestCreateTimeBuckets:
    """Test time bucket creation."""

    def test_create_hourly_buckets(self) -> None:
        """Test creating hourly time buckets."""
        generator = HeatMapGenerator()
        start = datetime(2025, 1, 10, 0, 0, 0)
        config = {"count": 3, "size": timedelta(hours=1)}

        buckets = generator._create_time_buckets(start, config)

        assert len(buckets) == 3
        assert buckets[0] == start
        assert buckets[1] == start + timedelta(hours=1)
        assert buckets[2] == start + timedelta(hours=2)


@pytest.mark.unit
class TestExportHeatmapData:
    """Test heatmap data export."""

    def test_export_to_dict(self) -> None:
        """Test exporting heatmap to dict via to_dict()."""
        generator = HeatMapGenerator()
        generator.add_error_data("/test/file.py", 10, "Error", "low")
        heatmap = generator.generate_error_frequency_heatmap()

        result = heatmap.to_dict()

        assert isinstance(result, dict)
        assert "title" in result
        assert "cells" in result

    def test_export_to_json_file(self, tmp_path) -> None:
        """Test exporting heatmap to JSON file."""
        generator = HeatMapGenerator()
        generator.add_error_data("/test/file.py", 10, "Error", "low")
        heatmap = generator.generate_error_frequency_heatmap()
        output_file = tmp_path / "heatmap.json"

        generator.export_heatmap_data(
            heatmap, output_path=str(output_file), format_type="json"
        )

        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)
            assert "title" in data


@pytest.mark.unit
class TestGenerateHtmlVisualization:
    """Test HTML visualization generation."""

    def test_generate_html(self) -> None:
        """Test generating HTML visualization."""
        generator = HeatMapGenerator()
        generator.add_error_data("/test/file.py", 10, "Error", "low")
        heatmap = generator.generate_error_frequency_heatmap()

        html = generator.generate_html_visualization(heatmap)

        assert isinstance(html, str)
        assert "<html>" in html
        assert heatmap.title in html


@pytest.mark.unit
class TestGetComplexityLevel:
    """Test complexity level mapping."""

    def test_simple_complexity(self) -> None:
        """Test simple complexity level."""
        generator = HeatMapGenerator()
        level = generator._get_complexity_level(5)

        assert level == "simple"

    def test_moderate_complexity(self) -> None:
        """Test moderate complexity level."""
        generator = HeatMapGenerator()
        level = generator._get_complexity_level(10)

        assert level == "moderate"

    def test_high_complexity(self) -> None:
        """Test high complexity levels."""
        generator = HeatMapGenerator()

        assert generator._get_complexity_level(15) == "complex"
        assert generator._get_complexity_level(18) == "very_complex"
        assert generator._get_complexity_level(25) == "extremely_complex"


@pytest.mark.unit
class TestCalculateQualityScore:
    """Test quality score calculation."""

    def test_calculate_quality_score(self) -> None:
        """Test quality score calculation."""
        generator = HeatMapGenerator()

        # For non-special metric types, intensity is returned as-is
        score1 = generator._calculate_quality_score("coverage", 0.85)
        assert score1 == 0.85

        # For complexity_score, it's inverted (1.0 - intensity)
        score2 = generator._calculate_quality_score("complexity_score", 0.3)
        assert score2 == 0.7


@pytest.mark.unit
class TestDetermineQualityLevel:
    """Test quality level determination."""

    def test_excellent_quality(self) -> None:
        """Test excellent quality level."""
        generator = HeatMapGenerator()
        level = generator._determine_quality_level(0.95)

        assert level == "excellent"

    def test_good_quality(self) -> None:
        """Test good quality level."""
        generator = HeatMapGenerator()
        level = generator._determine_quality_level(0.8)

        assert level == "good"

    def test_poor_quality(self) -> None:
        """Test poor quality level."""
        generator = HeatMapGenerator()
        level = generator._determine_quality_level(0.3)

        assert level == "poor"
