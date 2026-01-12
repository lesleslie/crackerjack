"""Unit tests for AdvancedOptimizer.

Tests resource metrics collection, scaling analysis, optimization recommendations,
data compaction, and connection pooling.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

import pytest

from crackerjack.services.ai.advanced_optimizer import (
    ConnectionPool,
    DataCompactionManager,
    OptimizationRecommendation,
    PerformanceProfile,
    ResourceMetrics,
    ScalingMetrics,
    AdvancedOptimizer,
)


@pytest.mark.unit
class TestResourceMetricsDataClass:
    """Test ResourceMetrics dataclass."""

    def test_resource_metrics_creation(self) -> None:
        """Test ResourceMetrics dataclass creation."""
        timestamp = datetime.now(timezone.utc)
        metrics = ResourceMetrics(
            cpu_percent=45.5,
            memory_percent=60.2,
            disk_usage_percent=75.0,
            network_io={"sent": 1000, "received": 2000},
            active_connections=5,
            thread_count=10,
            file_descriptors=100,
            timestamp=timestamp,
        )

        assert metrics.cpu_percent == 45.5
        assert metrics.memory_percent == 60.2
        assert metrics.disk_usage_percent == 75.0
        assert metrics.network_io == {"sent": 1000, "received": 2000}
        assert metrics.active_connections == 5
        assert metrics.thread_count == 10
        assert metrics.file_descriptors == 100
        assert metrics.timestamp == timestamp

    def test_resource_metrics_to_dict(self) -> None:
        """Test ResourceMetrics to_dict method."""
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=70.0,
            disk_usage_percent=80.0,
            network_io={},
            active_connections=3,
            thread_count=8,
            file_descriptors=50,
        )

        result = metrics.to_dict()

        assert result["cpu_percent"] == 50.0
        assert result["memory_percent"] == 70.0
        assert "timestamp" in result
        assert result["active_connections"] == 3


@pytest.mark.unit
class TestPerformanceProfileDataClass:
    """Test PerformanceProfile dataclass."""

    def test_performance_profile_creation(self) -> None:
        """Test PerformanceProfile dataclass creation."""
        profile = PerformanceProfile(
            workload_type="continuous_integration",
            concurrent_clients=10,
            data_retention_days=30,
            analysis_frequency_minutes=15,
            resource_limits={"max_memory_gb": 8, "max_cpu_cores": 4},
            optimization_strategy="balanced",
        )

        assert profile.workload_type == "continuous_integration"
        assert profile.concurrent_clients == 10
        assert profile.data_retention_days == 30
        assert profile.analysis_frequency_minutes == 15
        assert profile.resource_limits["max_memory_gb"] == 8
        assert profile.optimization_strategy == "balanced"

    def test_performance_profile_to_dict(self) -> None:
        """Test PerformanceProfile to_dict method."""
        profile = PerformanceProfile(
            workload_type="batch_processing",
            concurrent_clients=5,
            data_retention_days=7,
            analysis_frequency_minutes=60,
            resource_limits={},
            optimization_strategy="performance",
        )

        result = profile.to_dict()

        assert result["workload_type"] == "batch_processing"
        assert result["optimization_strategy"] == "performance"


@pytest.mark.unit
class TestOptimizationRecommendationDataClass:
    """Test OptimizationRecommendation dataclass."""

    def test_optimization_recommendation_creation(self) -> None:
        """Test OptimizationRecommendation dataclass creation."""
        recommendation = OptimizationRecommendation(
            category="memory",
            priority="high",
            title="Reduce memory usage",
            description="Implement lazy loading for large datasets",
            impact="30% reduction in memory footprint",
            implementation="Add DataLoader with lazy=True parameter",
            estimated_improvement="2-3 weeks",
            resource_cost="low",
            risk_level="low",
        )

        assert recommendation.category == "memory"
        assert recommendation.priority == "high"
        assert recommendation.title == "Reduce memory usage"
        assert recommendation.impact == "30% reduction in memory footprint"
        assert recommendation.risk_level == "low"

    def test_optimization_recommendation_to_dict(self) -> None:
        """Test OptimizationRecommendation to_dict method."""
        recommendation = OptimizationRecommendation(
            category="cpu",
            priority="medium",
            title="Optimize CPU usage",
            description="Use caching for expensive computations",
            impact="20% faster execution",
            implementation="Add Redis cache layer",
            estimated_improvement="1 week",
            resource_cost="medium",
            risk_level="medium",
        )

        result = recommendation.to_dict()

        assert result["category"] == "cpu"
        assert result["priority"] == "medium"
        assert result["title"] == "Optimize CPU usage"


@pytest.mark.unit
class TestScalingMetricsDataClass:
    """Test ScalingMetrics dataclass."""

    def test_scaling_metrics_creation(self) -> None:
        """Test ScalingMetrics dataclass creation."""
        metrics = ScalingMetrics(
            current_load=0.65,
            projected_load=0.85,
            response_time_p95=250.5,
            error_rate=0.01,
            memory_pressure=0.7,
            cpu_saturation=0.8,
            recommended_scale_factor=1.5,
            confidence_score=0.9,
        )

        assert metrics.current_load == 0.65
        assert metrics.projected_load == 0.85
        assert metrics.response_time_p95 == 250.5
        assert metrics.error_rate == 0.01
        assert metrics.memory_pressure == 0.7
        assert metrics.cpu_saturation == 0.8
        assert metrics.recommended_scale_factor == 1.5
        assert metrics.confidence_score == 0.9

    def test_scaling_metrics_to_dict(self) -> None:
        """Test ScalingMetrics to_dict method."""
        metrics = ScalingMetrics(
            current_load=0.5,
            projected_load=0.6,
            response_time_p95=100.0,
            error_rate=0.001,
            memory_pressure=0.4,
            cpu_saturation=0.5,
            recommended_scale_factor=1.0,
            confidence_score=0.95,
        )

        result = metrics.to_dict()

        assert result["current_load"] == 0.5
        assert result["recommended_scale_factor"] == 1.0
        assert result["confidence_score"] == 0.95


@pytest.mark.unit
class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_initialization(self) -> None:
        """Test ConnectionPool initialization."""
        pool = ConnectionPool(
            max_connections=100,
            cleanup_interval=300,
        )

        assert pool.max_connections == 100
        assert pool.cleanup_interval == 300
        assert len(pool.connections) == 0
        assert len(pool.connection_stats) == 0

    def test_add_connection(self) -> None:
        """Test adding a connection to the pool."""
        pool = ConnectionPool(max_connections=10)
        mock_websocket = Mock()

        pool.add_connection(
            connection_id="conn_1",
            websocket=mock_websocket,
            metadata={"user": "test"},
        )

        assert "conn_1" in pool.connections
        assert "conn_1" in pool.connection_stats
        assert pool.connection_stats["conn_1"]["metadata"]["user"] == "test"
        assert pool.connection_stats["conn_1"]["message_count"] == 0

    def test_add_connection_evicts_oldest_when_full(self) -> None:
        """Test that oldest connection is evicted when pool is full.

        NOTE: Deadlock bug has been fixed by changing threading.Lock to threading.RLock.
        The reentrant lock allows the same thread to acquire the lock multiple times,
        preventing deadlock when add_connection() calls remove_connection() while holding the lock.
        """
        pool = ConnectionPool(max_connections=2)

        # Add two connections to fill pool
        pool.add_connection("conn_1", Mock(), metadata={"order": 1})
        import time
        time.sleep(0.01)  # Small delay to ensure different timestamps
        pool.add_connection("conn_2", Mock(), metadata={"order": 2})

        # Add third connection - should evict conn_1 (oldest)
        pool.add_connection("conn_3", Mock(), metadata={"order": 3})

        assert "conn_1" not in pool.connections  # Evicted
        assert "conn_2" in pool.connections
        assert "conn_3" in pool.connections

    def test_remove_connection(self) -> None:
        """Test removing a connection from the pool."""
        pool = ConnectionPool(max_connections=10)
        mock_websocket = Mock()

        pool.add_connection("conn_1", mock_websocket)
        pool.remove_connection("conn_1")

        assert "conn_1" not in pool.connections
        assert "conn_1" not in pool.connection_stats

    def test_update_activity(self) -> None:
        """Test updating connection activity."""
        pool = ConnectionPool(max_connections=10)

        pool.add_connection("conn_1", Mock())
        initial_message_count = pool.connection_stats["conn_1"]["message_count"]

        pool.update_activity("conn_1")

        assert pool.connection_stats["conn_1"]["message_count"] == initial_message_count + 1

    def test_get_stats(self) -> None:
        """Test getting pool statistics."""
        pool = ConnectionPool(max_connections=10)

        pool.add_connection("conn_1", Mock())
        pool.add_connection("conn_2", Mock())
        pool.update_activity("conn_1")
        pool.update_activity("conn_2")

        stats = pool.get_stats()

        assert stats["total_connections"] == 2
        assert stats["active_connections"] == 2
        assert stats["max_connections"] == 10
        assert stats["utilization_percent"] == 20.0
        assert stats["average_message_count"] == 1.0


@pytest.mark.unit
class TestDataCompactionManager:
    """Test DataCompactionManager class."""

    def test_initialization(self) -> None:
        """Test DataCompactionManager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DataCompactionManager(
                storage_dir=Path(tmpdir),
                max_storage_gb=10.0,
            )

            assert manager.storage_dir == Path(tmpdir)
            assert manager.max_storage_bytes == 10 * 1024**3
            assert len(manager.compaction_rules) > 0
            assert "metrics_raw" in manager.compaction_rules

    def test_load_compaction_rules(self) -> None:
        """Test loading compaction rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DataCompactionManager(storage_dir=Path(tmpdir))

            rules = manager.compaction_rules

            # Should have rules for different data types
            assert "metrics_raw" in rules
            assert "metrics_hourly" in rules
            assert "metrics_daily" in rules
            assert "error_patterns" in rules
            assert "dependency_graphs" in rules

    def test_create_metrics_raw_config(self) -> None:
        """Test metrics raw configuration."""
        config = DataCompactionManager._create_metrics_raw_config()

        # Config has exactly 3 fields (not 5)
        assert "retention_days" in config
        assert "compaction_interval_hours" in config
        assert "aggregation_method" in config
        assert config["retention_days"] == 7
        assert config["aggregation_method"] == "downsample"

    def test_create_metrics_hourly_config(self) -> None:
        """Test metrics hourly configuration."""
        config = DataCompactionManager._create_metrics_hourly_config()

        # Config has exactly 3 fields (not 5)
        assert "retention_days" in config
        assert "compaction_interval_hours" in config
        assert "aggregation_method" in config
        assert config["retention_days"] == 30
        assert config["aggregation_method"] == "statistical"

    def test_create_metrics_daily_config(self) -> None:
        """Test metrics daily configuration."""
        config = DataCompactionManager._create_metrics_daily_config()

        # Config has exactly 3 fields (not 5)
        assert "retention_days" in config
        assert "compaction_interval_hours" in config
        assert "aggregation_method" in config
        assert config["retention_days"] == 365
        assert config["aggregation_method"] == "statistical"

    def test_create_error_patterns_config(self) -> None:
        """Test error patterns configuration."""
        config = DataCompactionManager._create_error_patterns_config()

        # Config has exactly 3 fields (not 5)
        assert "retention_days" in config
        assert "compaction_interval_hours" in config
        assert "aggregation_method" in config
        assert config["retention_days"] == 90
        assert config["aggregation_method"] == "deduplication"

    def test_create_dependency_graphs_config(self) -> None:
        """Test dependency graphs configuration."""
        config = DataCompactionManager._create_dependency_graphs_config()

        # Config has exactly 3 fields (not 5)
        assert "retention_days" in config
        assert "compaction_interval_hours" in config
        assert "aggregation_method" in config
        assert config["retention_days"] == 30
        assert config["aggregation_method"] == "latest_version"


@pytest.mark.unit
class TestAdvancedOptimizer:
    """Test AdvancedOptimizer class."""

    def test_initialization(self) -> None:
        """Test AdvancedOptimizer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            assert optimizer.config_dir == config_dir
            assert optimizer.storage_dir == storage_dir
            assert optimizer.connection_pool is not None
            assert optimizer.compaction_manager is not None

    def test_collect_resource_metrics(self) -> None:
        """Test collecting resource metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            metrics = optimizer.collect_resource_metrics()

            assert isinstance(metrics, ResourceMetrics)
            assert hasattr(metrics, "cpu_percent")
            assert hasattr(metrics, "memory_percent")
            assert hasattr(metrics, "disk_usage_percent")

    def test_analyze_scaling_needs(self) -> None:
        """Test analyzing scaling needs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            scaling = optimizer.analyze_scaling_needs()

            assert isinstance(scaling, ScalingMetrics)
            assert hasattr(scaling, "current_load")
            assert hasattr(scaling, "recommended_scale_factor")
            assert hasattr(scaling, "confidence_score")

    def test_generate_optimization_recommendations(self) -> None:
        """Test generating optimization recommendations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            recommendations = optimizer.generate_optimization_recommendations()

            assert isinstance(recommendations, list)
            # May be empty if no issues detected
            for rec in recommendations:
                assert isinstance(rec, OptimizationRecommendation)

    def test_optimize_configuration(self) -> None:
        """Test optimizing configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            result = optimizer.optimize_configuration(strategy="balanced")

            assert isinstance(result, dict)
            # Should return error when no metrics available
            if result["status"] == "error":
                assert "message" in result
            else:
                # Success case has these fields
                assert "optimizations_applied" in result
                assert "timestamp" in result

    def test_get_advanced_status(self) -> None:
        """Test getting advanced optimizer status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            status = optimizer.get_advanced_status()

            assert isinstance(status, dict)
            assert "health_score" in status
            assert "resource_metrics" in status
            assert "scaling_metrics" in status


@pytest.mark.unit
class TestAdvancedOptimizerAsyncMethods:
    """Test AdvancedOptimizer async methods."""

    def test_run_optimization_cycle(self) -> None:
        """Test running optimization cycle asynchronously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            storage_dir = Path(tmpdir) / "storage"
            storage_dir.mkdir()

            optimizer = AdvancedOptimizer(
                config_dir=config_dir,
                storage_dir=storage_dir,
            )

            import asyncio

            async def test_async():
                result = await optimizer.run_optimization_cycle()
                return result

            result = asyncio.run(test_async())

            assert isinstance(result, dict)
            # Actual fields from implementation (not cycle_timestamp/optimizations_performed)
            assert "status" in result
            assert "metrics" in result
            assert "scaling_analysis" in result
            assert "recommendations" in result
            assert "timestamp" in result  # NOT cycle_timestamp!
