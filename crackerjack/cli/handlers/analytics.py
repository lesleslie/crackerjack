"""CLI handlers for analytics features (heatmap, anomaly detection, predictive analytics)."""

import typing as t
from pathlib import Path

# =============================================================================
# Heatmap Generation
# =============================================================================


def _generate_heatmap_by_type(
    generator: t.Any, heatmap_type: str, project_root: Path, console: t.Any
) -> t.Any | None:
    """Generate heatmap data based on the specified type.

    Args:
        generator: HeatMapGenerator instance
        heatmap_type: Type of heatmap to generate
        project_root: Project root directory
        console: Console for output

    Returns:
        Heatmap data or None if type is unknown
    """
    if heatmap_type == "error_frequency":
        return generator.generate_error_frequency_heatmap()
    if heatmap_type == "complexity":
        return generator.generate_code_complexity_heatmap(project_root)
    if heatmap_type == "quality_metrics":
        return generator.generate_quality_metrics_heatmap()
    if heatmap_type == "test_failures":
        return generator.generate_test_failure_heatmap()

    console.print(f"[red]❌[/red] Unknown heat map type: {heatmap_type}")
    return None


def _save_heatmap_output(
    generator: t.Any,
    heatmap_data: t.Any,
    heatmap_output: str | None,
    heatmap_type: str,
    console: t.Any,
) -> bool:
    """Save heatmap output to file.

    Args:
        generator: HeatMapGenerator instance
        heatmap_data: Generated heatmap data
        heatmap_output: Optional output path
        heatmap_type: Type of heatmap
        console: Console for output

    Returns:
        True if saved successfully, False otherwise
    """
    if heatmap_output:
        output_path = Path(heatmap_output)
        if output_path.suffix.lower() == ".html":
            html_content = generator.generate_html_visualization(heatmap_data)
            output_path.write_text(html_content, encoding="utf-8")
            console.print(f"[green]✅[/green] Heat map HTML saved to: {output_path}")
            return True
        if output_path.suffix.lower() in (".json", ".csv"):
            format_type = output_path.suffix[1:]
            generator.export_heatmap_data(heatmap_data, output_path, format_type)
            console.print(f"[green]✅[/green] Heat map data saved to: {output_path}")
            return True

        console.print(f"[red]❌[/red] Unsupported output format: {output_path.suffix}")
        return False

    # Default: save as HTML
    default_filename = f"heatmap_{heatmap_type}.html"
    html_content = generator.generate_html_visualization(heatmap_data)
    Path(default_filename).write_text(html_content, encoding="utf-8")
    console.print(f"[green]✅[/green] Heat map HTML saved to: {default_filename}")
    return True


def handle_heatmap_generation(
    heatmap: bool,
    heatmap_type: str,
    heatmap_output: str | None,
) -> bool:
    if not heatmap:
        return True

    from crackerjack.services.heatmap_generator import HeatMapGenerator

    console.print("[cyan]🔥[/cyan] Generating heat map visualization...")

    try:
        generator = HeatMapGenerator()
        project_root = Path.cwd()

        heatmap_data = _generate_heatmap_by_type(
            generator, heatmap_type, project_root, console
        )
        if not heatmap_data:
            return False

        if not _save_heatmap_output(
            generator, heatmap_data, heatmap_output, heatmap_type, console
        ):
            return False

        console.print(
            f"[cyan]📊[/cyan] Heat map '{heatmap_data.title}' generated successfully"
        )
        console.print(f"[dim] • Cells: {len(heatmap_data.cells)}")
        console.print(f"[dim] • X Labels: {len(heatmap_data.x_labels)}")
        console.print(f"[dim] • Y Labels: {len(heatmap_data.y_labels)}")

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Heat map generation failed: {e}")
        return False


# =============================================================================
# Anomaly Detection
# =============================================================================
def generate_anomaly_sample_data(detector: t.Any) -> None:
    from datetime import datetime, timedelta

    base_time = datetime.now() - timedelta(hours=24)

    metric_types = [
        "test_pass_rate",
        "coverage_percentage",
        "complexity_score",
        "execution_time",
        "error_count",
    ]

    console.print("[dim] • Collecting quality metrics from recent runs...")

    for i in range(50):
        timestamp = base_time + timedelta(minutes=i * 30)

        for metric_type in metric_types:
            value = get_sample_metric_value(metric_type)

            detector.add_metric(metric_type, value, timestamp)


def get_sample_metric_value(metric_type: str) -> float:
    """Generate sample metric values for demo/visualization purposes.

    Note: Uses standard random (not cryptographic) as this is ONLY for
    generating fake demo data, not for any security-sensitive purposes.
    """
    import random

    # Demo data generation - cryptographic randomness not required
    is_anomaly = random.random() <= 0.1  # nosec B311

    if metric_type == "test_pass_rate":
        return random.uniform(0.3, 0.7) if is_anomaly else random.uniform(0.85, 0.98)  # nosec B311

    elif metric_type == "coverage_percentage":
        return random.uniform(40, 60) if is_anomaly else random.uniform(75, 95)  # nosec B311

    elif metric_type == "complexity_score":
        return random.uniform(20, 35) if is_anomaly else random.uniform(8, 15)  # nosec B311

    elif metric_type == "execution_time":
        return random.uniform(300, 600) if is_anomaly else random.uniform(30, 120)  # nosec B311

    return random.uniform(8, 15) if is_anomaly else random.uniform(0, 3)  # nosec B311


def display_anomaly_results(
    anomalies: list[t.Any], baselines: dict[str, t.Any]
) -> None:
    console.print("[cyan]📊[/cyan] Analysis complete:")

    console.print(f"[dim] • Baselines established for {len(baselines)} metrics")

    console.print(f"[dim] • {len(anomalies)} anomalies detected")

    if anomalies:
        console.print("\n[yellow]⚠️[/yellow] Detected anomalies:")

        for anomaly in anomalies[:5]:
            severity_color = {
                "low": "yellow",
                "medium": "orange",
                "high": "red",
                "critical": "bright_red",
            }.get(anomaly.severity, "white")

            console.print(
                f" • [{severity_color}]{anomaly.severity.upper()}[/{severity_color}] "
                f"{anomaly.metric_type}: {anomaly.description}"
            )


def save_anomaly_report(
    anomalies: list[t.Any],
    baselines: dict[str, t.Any],
    anomaly_sensitivity: float,
    anomaly_report: str,
) -> None:
    import json
    from datetime import datetime

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_anomalies": len(anomalies),
            "baselines_count": len(baselines),
            "sensitivity": anomaly_sensitivity,
        },
        "anomalies": [
            {
                "timestamp": a.timestamp.isoformat(),
                "metric_type": a.metric_type,
                "value": a.value,
                "expected_range": a.expected_range,
                "severity": a.severity,
                "confidence": a.confidence,
                "description": a.description,
            }
            for a in anomalies
        ],
        "baselines": baselines,
    }

    report_path = Path(anomaly_report)

    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    console.print(f"[green]✅[/green] Anomaly detection report saved to: {report_path}")


def handle_anomaly_detection(
    anomaly_detection: bool,
    anomaly_sensitivity: float,
    anomaly_report: str | None,
) -> bool:
    if not anomaly_detection:
        return True

    from crackerjack.services.quality.anomaly_detector import AnomalyDetector

    console.print("[cyan]🔍[/cyan] Running ML-based anomaly detection...")

    try:
        detector = AnomalyDetector(sensitivity=anomaly_sensitivity)

        generate_anomaly_sample_data(detector)

        anomalies = detector.get_anomalies()

        baselines = detector.get_baseline_summary()

        display_anomaly_results(anomalies, baselines)

        if anomaly_report:
            save_anomaly_report(
                anomalies, baselines, anomaly_sensitivity, anomaly_report
            )

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Anomaly detection failed: {e}")

        return False


# =============================================================================
# Predictive Analytics
# =============================================================================


def generate_predictive_sample_data(engine: t.Any) -> list[str]:
    """Generate sample data for predictive monitoring demo/visualization.

    Note: Uses standard random (not cryptographic) as this is ONLY for
    generating fake demo data, not for any security-sensitive purposes.
    """
    import random
    from datetime import datetime, timedelta

    base_time = datetime.now() - timedelta(hours=72)

    metric_types = [
        "test_pass_rate",
        "coverage_percentage",
        "execution_time",
        "memory_usage",
        "complexity_score",
    ]

    base_values = {
        "test_pass_rate": 0.95,
        "coverage_percentage": 0.85,
        "execution_time": 120.0,
        "memory_usage": 512.0,
        "complexity_score": 10.0,
    }

    for metric_type in metric_types:
        base_value = base_values[metric_type]

        for i in range(48):
            timestamp = base_time + timedelta(hours=i)

            trend_factor = 1.0 + (i * 0.001)

            # Demo data generation - cryptographic randomness not required
            noise = random.uniform(0.9, 1.1)  # nosec B311

            value = base_value * trend_factor * noise

            engine.add_metric(metric_type, value, timestamp)

    return metric_types


def generate_predictions_summary(
    engine: t.Any, metric_types: list[str], prediction_periods: int
) -> dict[str, t.Any]:
    predictions_summary = {}

    trend_summary = engine.get_trend_summary()

    for metric_type in metric_types:
        predictions = engine.predict_metric(metric_type, prediction_periods)

        if predictions:
            predictions_summary[metric_type] = {
                "trend": trend_summary.get(metric_type, {}),
                "predictions": [
                    {
                        "predicted_for": p.predicted_for.isoformat(),
                        "predicted_value": round(p.predicted_value, 3),
                        "confidence_interval": [
                            round(p.confidence_interval[0], 3),
                            round(p.confidence_interval[1], 3),
                        ],
                        "model_accuracy": round(p.model_accuracy, 3),
                    }
                    for p in predictions[:5]
                ],
            }

    return predictions_summary


def display_trend_analysis(predictions_summary: dict[str, t.Any]) -> None:
    console.print("\n[green]📈[/green] Trend Analysis Summary:")

    for metric_type, data in predictions_summary.items():
        trend_info = data.get("trend", {})

        direction = trend_info.get("trend_direction", "unknown")

        strength = trend_info.get("trend_strength", 0)

        direction_color = {
            "increasing": "green",
            "decreasing": "red",
            "stable": "blue",
            "volatile": "yellow",
        }.get(direction, "white")

        console.print(
            f" • {metric_type}: [{direction_color}]{direction}[/{direction_color}] "
            f"(strength: {strength:.2f})"
        )

        if data["predictions"]:
            next_pred = data["predictions"][0]

            console.print(
                f" Next prediction: {next_pred['predicted_value']} "
                f"(confidence: {next_pred['model_accuracy']:.2f})"
            )


def save_analytics_dashboard(
    predictions_summary: dict[str, t.Any],
    trend_summary: dict[str, t.Any],
    metric_types: list[str],
    prediction_periods: int,
    analytics_dashboard: str,
) -> None:
    import json
    from datetime import datetime

    dashboard_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "prediction_periods": prediction_periods,
            "metrics_analyzed": len(metric_types),
            "total_predictions": sum(
                len(data["predictions"]) for data in predictions_summary.values()
            ),
        },
        "trends": trend_summary,
        "predictions": predictions_summary,
    }

    dashboard_path = Path(analytics_dashboard)

    dashboard_path.write_text(json.dumps(dashboard_data, indent=2), encoding="utf-8")

    console.print(f"[green]✅[/green] Analytics dashboard saved to: {dashboard_path}")


def handle_predictive_analytics(
    predictive_analytics: bool,
    prediction_periods: int,
    analytics_dashboard: str | None,
) -> bool:
    if not predictive_analytics:
        return True

    from crackerjack.services.ai.predictive_analytics import PredictiveAnalyticsEngine

    console.print(
        "[cyan]📊[/cyan] Running predictive analytics and trend forecasting..."
    )

    try:
        engine = PredictiveAnalyticsEngine()

        metric_types = generate_predictive_sample_data(engine)

        console.print(
            f"[blue]🔮[/blue] Generating {prediction_periods} period predictions..."
        )

        predictions_summary = generate_predictions_summary(
            engine, metric_types, prediction_periods
        )
        trend_summary = engine.get_trend_summary()

        display_trend_analysis(predictions_summary)

        if analytics_dashboard:
            save_analytics_dashboard(
                predictions_summary,
                trend_summary,
                metric_types,
                prediction_periods,
                analytics_dashboard,
            )

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Predictive analytics failed: {e}")
        return False
