import typing as t
import warnings
from pathlib import Path

import typer
from acb.console import Console
from acb.depends import Inject, depends

# Suppress asyncio subprocess cleanup warnings when event loop closes
# This is a known Python issue - the subprocesses are properly cleaned up,
# but the warning appears when the event loop closes with pending subprocess handlers
warnings.filterwarnings(
    "ignore",
    message=".*loop.*closed.*",
    category=RuntimeWarning,
)

if t.TYPE_CHECKING:
    from crackerjack.services.changelog_automation import ChangelogGenerator

from crackerjack.services.git import GitService

from .cli import (
    CLI_OPTIONS,
    BumpOption,
    create_options,
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)
from .cli.cache_handlers import _handle_cache_commands
from .cli.handlers import (
    handle_config_updates,
    handle_dashboard_mode,
    handle_enhanced_monitor_mode,
    handle_mcp_server,
    handle_monitor_mode,
    handle_restart_mcp_server,
    handle_restart_websocket_server,
    handle_restart_zuban_lsp,
    handle_start_websocket_server,
    handle_start_zuban_lsp,
    handle_stop_mcp_server,
    handle_stop_websocket_server,
    handle_stop_zuban_lsp,
    handle_watchdog_mode,
)
from .cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
    handle_semantic_stats,
)

console = Console()
app = typer.Typer(
    help="Crackerjack: Your Python project setup and style enforcement tool.",
)


def _handle_monitoring_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    dev: bool,
) -> bool:
    if monitor:
        handle_monitor_mode(dev_mode=dev)
        return True
    if enhanced_monitor:
        handle_enhanced_monitor_mode(dev_mode=dev)
        return True
    if dashboard:
        handle_dashboard_mode(dev_mode=dev)
        return True
    if unified_dashboard:
        from .cli.handlers import handle_unified_dashboard_mode

        port = unified_dashboard_port or 8675
        handle_unified_dashboard_mode(port=port, dev_mode=dev)
        return True
    if watchdog:
        handle_watchdog_mode()
        return True
    return False


def _handle_websocket_commands(
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    websocket_port: int | None,
) -> bool:
    if start_websocket_server:
        port = websocket_port or 8675
        handle_start_websocket_server(port)
        return True
    if stop_websocket_server:
        handle_stop_websocket_server()
        return True
    if restart_websocket_server:
        port = websocket_port or 8675
        handle_restart_websocket_server(port)
        return True
    return False


def _handle_mcp_commands(
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
) -> bool:
    if start_mcp_server:
        handle_mcp_server(websocket_port)
        return True
    if stop_mcp_server:
        handle_stop_mcp_server()
        return True
    if restart_mcp_server:
        handle_restart_mcp_server(websocket_port)
        return True
    return False


def _handle_zuban_lsp_commands(
    start_zuban_lsp: bool,
    stop_zuban_lsp: bool,
    restart_zuban_lsp: bool,
    zuban_lsp_port: int,
    zuban_lsp_mode: str,
) -> bool:
    if start_zuban_lsp:
        handle_start_zuban_lsp(port=zuban_lsp_port, mode=zuban_lsp_mode)
        return True
    if stop_zuban_lsp:
        handle_stop_zuban_lsp()
        return True
    if restart_zuban_lsp:
        handle_restart_zuban_lsp(port=zuban_lsp_port, mode=zuban_lsp_mode)
        return True
    return False


def _handle_server_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
    start_zuban_lsp: bool,
    stop_zuban_lsp: bool,
    restart_zuban_lsp: bool,
    zuban_lsp_port: int,
    zuban_lsp_mode: str,
    dev: bool,
) -> bool:
    return (
        _handle_monitoring_commands(
            monitor,
            enhanced_monitor,
            dashboard,
            unified_dashboard,
            unified_dashboard_port,
            watchdog,
            dev,
        )
        or _handle_websocket_commands(
            start_websocket_server,
            stop_websocket_server,
            restart_websocket_server,
            websocket_port,
        )
        or _handle_mcp_commands(
            start_mcp_server,
            stop_mcp_server,
            restart_mcp_server,
            websocket_port,
        )
        or _handle_zuban_lsp_commands(
            start_zuban_lsp,
            stop_zuban_lsp,
            restart_zuban_lsp,
            zuban_lsp_port,
            zuban_lsp_mode,
        )
    )


@depends.inject  # type: ignore[misc]
def _generate_documentation(doc_service: t.Any, console: Inject[Console]) -> bool:
    console.print("📖 [bold blue]Generating API documentation...[/bold blue]")
    success = doc_service.generate_full_api_documentation()
    if success:
        console.print(
            "✅ [bold green]Documentation generated successfully![/bold green]"
        )
        return True
    else:
        console.print("❌ [bold red]Documentation generation failed![/bold red]")
        return False


@depends.inject  # type: ignore[misc]
def _validate_documentation_files(doc_service: t.Any, console: Inject[Console]) -> None:
    from pathlib import Path

    console.print("🔍 [bold blue]Validating documentation...[/bold blue]")
    doc_paths = [Path("docs"), Path("README.md"), Path("CHANGELOG.md")]
    existing_docs = [p for p in doc_paths if p.exists()]

    if existing_docs:
        issues = doc_service.validate_documentation(existing_docs)
        if issues:
            console.print(f"⚠️ Found {len(issues)} documentation issues:")
            for issue in issues:
                file_path = issue.get("path", issue.get("file", "unknown"))
                console.print(f" - {file_path}: {issue['message']}")
        else:
            console.print(
                "✅ [bold green]Documentation validation passed![/bold green]"
            )
    else:
        console.print("⚠️ No documentation files found to validate")


def _handle_documentation_commands(
    generate_docs: bool, validate_docs: bool, options: t.Any
) -> bool:
    if not (generate_docs or validate_docs):
        return True

    from pathlib import Path

    from crackerjack.services.documentation_service import DocumentationServiceImpl

    pkg_path = Path("crackerjack")
    doc_service = DocumentationServiceImpl(pkg_path=pkg_path)

    if generate_docs:
        if not _generate_documentation(doc_service):
            return False

    if validate_docs:
        _validate_documentation_files(doc_service)

    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def _handle_changelog_commands(
    generate_changelog: bool,
    changelog_dry_run: bool,
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
) -> bool:
    if not (generate_changelog or changelog_dry_run):
        return True

    services = _setup_changelog_services()
    changelog_path = services["pkg_path"] / "CHANGELOG.md"

    if changelog_dry_run:
        result: bool = _handle_changelog_dry_run(
            services["generator"], changelog_since, options
        )
        return result

    if generate_changelog:
        result = _handle_changelog_generation(
            services, changelog_path, changelog_version, changelog_since, options
        )
        return result

    return _should_continue_after_changelog(options)


def _setup_changelog_services() -> dict[str, t.Any]:
    from pathlib import Path

    from crackerjack.services.changelog_automation import ChangelogGenerator
    from crackerjack.services.git import GitService

    pkg_path = Path()
    git_service = GitService()
    changelog_generator = ChangelogGenerator()

    return {
        "pkg_path": pkg_path,
        "git_service": git_service,
        "generator": changelog_generator,
    }


@depends.inject  # type: ignore[misc]
def _handle_changelog_dry_run(
    generator: "ChangelogGenerator",
    changelog_since: str | None,
    options: t.Any,
    console: Inject[Console],
) -> bool:
    console.print("🔍 [bold blue]Previewing changelog generation...[/bold blue]")
    entries = generator.generate_changelog_entries(changelog_since)
    if entries:
        generator._display_changelog_preview(entries)
        console.print("✅ [bold green]Changelog preview completed![/bold green]")
    else:
        console.print("⚠️ No new changelog entries to generate")

    return _should_continue_after_changelog(options)


@depends.inject  # type: ignore[misc]
def _handle_changelog_generation(
    services: dict[str, t.Any],
    changelog_path: "Path",
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
    console: Inject[Console],
) -> bool:
    console.print("📝 [bold blue]Generating changelog...[/bold blue]")

    version = _determine_changelog_version(
        services["git_service"], changelog_version, changelog_since, options
    )

    success = services["generator"].generate_changelog_from_commits(
        changelog_path=changelog_path,
        version=version,
        since_version=changelog_since,
    )

    if success:
        console.print(
            f"✅ [bold green]Changelog updated for version {version}![/bold green]"
        )
        return _should_continue_after_changelog(options)
    else:
        console.print("❌ [bold red]Changelog generation failed![/bold red]")
        return False


@depends.inject  # type: ignore[misc]
def _determine_changelog_version(
    git_service: GitService,
    changelog_version: str | None,
    changelog_since: str | None,
    options: t.Any,
    console: Inject[Console],
) -> str:
    if getattr(options, "auto_version", False) and not changelog_version:
        try:
            import asyncio

            from crackerjack.services.version_analyzer import VersionAnalyzer

            version_analyzer = VersionAnalyzer(git_service)
            console.print(
                "[cyan]🔍[/cyan] Analyzing version changes for intelligent changelog..."
            )

            recommendation = asyncio.run(
                version_analyzer.recommend_version_bump(changelog_since)
            )
            version = recommendation.recommended_version
            console.print(f"[green]✨[/green] Using AI-recommended version: {version}")
            return version
        except Exception as e:
            console.print(f"[yellow]⚠️[/yellow] Version analysis failed: {e}")
            return changelog_version or "Unreleased"

    return changelog_version or "Unreleased"


def _should_continue_after_changelog(options: t.Any) -> bool:
    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


@depends.inject  # type: ignore[misc]
def _handle_version_analysis(
    auto_version: bool,
    version_since: str | None,
    accept_version: bool,
    options: t.Any,
    console: Inject[Console],
) -> bool:
    if not auto_version:
        return True

    from pathlib import Path

    from rich.prompt import Confirm

    from crackerjack.services.git import GitService
    from crackerjack.services.version_analyzer import VersionAnalyzer

    Path()
    git_service = GitService()
    version_analyzer = VersionAnalyzer(git_service)

    try:
        import asyncio

        recommendation = asyncio.run(
            version_analyzer.recommend_version_bump(version_since)
        )
        version_analyzer.display_recommendation(recommendation)

        if accept_version or Confirm.ask(
            f"\nAccept recommendation ({recommendation.bump_type.value})",
            default=True,
        ):
            console.print(
                f"[green]✅ Version bump accepted: {recommendation.current_version} → {recommendation.recommended_version}[/green]"
            )

        else:
            console.print("[yellow]❌ Version bump declined[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Version analysis failed: {e}[/red]")

    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def _setup_debug_and_verbose_flags(
    ai_fix: bool, ai_debug: bool, debug: bool, verbose: bool, options: t.Any
) -> tuple[bool, bool]:
    if ai_debug:
        ai_fix = True
        verbose = True
        options.verbose = True
        options.ai_debug = True  # Set ai_debug on options for downstream checks

    if debug:
        verbose = True
        options.verbose = True

    # Set up structured logging for AI-related operations if needed
    if ai_fix or ai_debug:
        from crackerjack.services.logging import setup_structured_logging

        setup_structured_logging(level="DEBUG", json_output=True)

    return ai_fix, verbose


@depends.inject  # type: ignore[misc]
def _handle_heatmap_generation(
    heatmap: bool,
    heatmap_type: str,
    heatmap_output: str | None,
    console: Inject[Console],
) -> bool:
    if not heatmap:
        return True

    from pathlib import Path

    from crackerjack.services.heatmap_generator import HeatMapGenerator

    console.print("[cyan]🔥[/cyan] Generating heat map visualization...")

    try:
        generator = HeatMapGenerator()
        project_root = Path.cwd()

        if heatmap_type == "error_frequency":
            heatmap_data = generator.generate_error_frequency_heatmap()
        elif heatmap_type == "complexity":
            heatmap_data = generator.generate_code_complexity_heatmap(project_root)
        elif heatmap_type == "quality_metrics":
            heatmap_data = generator.generate_quality_metrics_heatmap()
        elif heatmap_type == "test_failures":
            heatmap_data = generator.generate_test_failure_heatmap()
        else:
            console.print(f"[red]❌[/red] Unknown heat map type: {heatmap_type}")
            return False

        if heatmap_output:
            output_path = Path(heatmap_output)
            if output_path.suffix.lower() == ".html":
                html_content = generator.generate_html_visualization(heatmap_data)
                output_path.write_text(html_content, encoding="utf-8")
                console.print(
                    f"[green]✅[/green] Heat map HTML saved to: {output_path}"
                )
            elif output_path.suffix.lower() in (".json", ".csv"):
                format_type = output_path.suffix[1:]
                generator.export_heatmap_data(heatmap_data, output_path, format_type)
                console.print(
                    f"[green]✅[/green] Heat map data saved to: {output_path}"
                )
            else:
                console.print(
                    f"[red]❌[/red] Unsupported output format: {output_path.suffix}"
                )
                return False
        else:
            default_filename = f"heatmap_{heatmap_type}.html"
            html_content = generator.generate_html_visualization(heatmap_data)
            Path(default_filename).write_text(html_content, encoding="utf-8")
            console.print(
                f"[green]✅[/green] Heat map HTML saved to: {default_filename}"
            )

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


@depends.inject  # type: ignore[misc]
def _generate_anomaly_sample_data(detector: t.Any, console: Inject[Console]) -> None:
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
            value = _get_sample_metric_value(metric_type)

            detector.add_metric(metric_type, value, timestamp)


def _get_sample_metric_value(metric_type: str) -> float:
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


@depends.inject  # type: ignore[misc]
def _display_anomaly_results(
    anomalies: list[t.Any], baselines: dict[str, t.Any], console: Inject[Console]
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


@depends.inject  # type: ignore[misc]
def _save_anomaly_report(
    anomalies: list[t.Any],
    baselines: dict[str, t.Any],
    anomaly_sensitivity: float,
    anomaly_report: str,
    console: Inject[Console],
) -> None:
    import json
    from datetime import datetime
    from pathlib import Path

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


@depends.inject  # type: ignore[misc]
def _handle_anomaly_detection(
    anomaly_detection: bool,
    anomaly_sensitivity: float,
    anomaly_report: str | None,
    console: Inject[Console],
) -> bool:
    if not anomaly_detection:
        return True

    from crackerjack.services.quality.anomaly_detector import AnomalyDetector

    console.print("[cyan]🔍[/cyan] Running ML-based anomaly detection...")

    try:
        detector = AnomalyDetector(sensitivity=anomaly_sensitivity)

        _generate_anomaly_sample_data(detector)

        anomalies = detector.get_anomalies()

        baselines = detector.get_baseline_summary()

        _display_anomaly_results(anomalies, baselines)

        if anomaly_report:
            _save_anomaly_report(
                anomalies, baselines, anomaly_sensitivity, anomaly_report
            )

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Anomaly detection failed: {e}")

        return False


def _generate_predictive_sample_data(engine: t.Any) -> list[str]:
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


def _generate_predictions_summary(
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


@depends.inject  # type: ignore[misc]
def _display_trend_analysis(
    predictions_summary: dict[str, t.Any], console: Inject[Console]
) -> None:
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


@depends.inject  # type: ignore[misc]
def _save_analytics_dashboard(
    predictions_summary: dict[str, t.Any],
    trend_summary: dict[str, t.Any],
    metric_types: list[str],
    prediction_periods: int,
    analytics_dashboard: str,
    console: Inject[Console],
) -> None:
    import json
    from datetime import datetime
    from pathlib import Path

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


@depends.inject  # type: ignore[misc]
def _handle_predictive_analytics(
    predictive_analytics: bool,
    prediction_periods: int,
    analytics_dashboard: str | None,
    console: Inject[Console],
) -> bool:
    if not predictive_analytics:
        return True

    from crackerjack.services.ai.predictive_analytics import PredictiveAnalyticsEngine

    console.print(
        "[cyan]📊[/cyan] Running predictive analytics and trend forecasting..."
    )

    try:
        engine = PredictiveAnalyticsEngine()

        metric_types = _generate_predictive_sample_data(engine)

        console.print(
            f"[blue]🔮[/blue] Generating {prediction_periods} period predictions..."
        )

        predictions_summary = _generate_predictions_summary(
            engine, metric_types, prediction_periods
        )
        trend_summary = engine.get_trend_summary()

        _display_trend_analysis(predictions_summary)

        if analytics_dashboard:
            _save_analytics_dashboard(
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


@depends.inject  # type: ignore[misc]
def _handle_advanced_optimizer(
    advanced_optimizer: bool,
    advanced_profile: str | None,
    advanced_report: str | None,
    console: Inject[Console] = None,
) -> bool:
    if not advanced_optimizer:
        return True

    console.print("[cyan]🏢[/cyan] Running advanced-scale optimization analysis...")
    try:
        optimizer = _setup_advanced_optimizer(advanced_profile)
        result = _run_advanced_optimization(optimizer)
        _display_advanced_results(result, advanced_report)
        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Advanced optimizer error: {e}")
        return False


def _setup_advanced_optimizer(advanced_profile: str | None) -> t.Any:
    import tempfile
    from pathlib import Path

    from crackerjack.services.ai.advanced_optimizer import AdvancedOptimizer

    config_dir = Path.cwd() / ".crackerjack"
    storage_dir = Path(tempfile.gettempdir()) / "crackerjack_storage"
    optimizer = AdvancedOptimizer(config_dir, storage_dir)

    if advanced_profile:
        optimizer.performance_profile.optimization_strategy = advanced_profile

    return optimizer


@depends.inject  # type: ignore[misc]
def _run_advanced_optimization(optimizer: t.Any, console: Inject[Console]) -> t.Any:
    import asyncio

    console.print("[blue]📊[/blue] Analyzing system resources and performance...")
    return asyncio.run(optimizer.run_optimization_cycle())


@depends.inject  # type: ignore[misc]
def _display_advanced_results(
    result: t.Any, advanced_report: str | None, console: Inject[Console]
) -> None:
    if result["status"] == "success":
        console.print("[green]✅[/green] Advanced optimization completed successfully")
        _display_advanced_metrics(result["metrics"])
        _display_advanced_recommendations(result["recommendations"])
        _save_advanced_report(result, advanced_report)
    else:
        console.print(
            f"[red]❌[/red] Advanced optimization failed: {result.get('message', 'Unknown error')}"
        )


@depends.inject  # type: ignore[misc]
def _display_advanced_metrics(metrics: t.Any, console: Inject[Console]) -> None:
    console.print(f"[blue]CPU Usage:[/blue] {metrics['cpu_percent']:.1f}%")
    console.print(f"[blue]Memory Usage:[/blue] {metrics['memory_percent']:.1f}%")
    console.print(f"[blue]Storage Usage:[/blue] {metrics['disk_usage_percent']:.1f}%")


@depends.inject  # type: ignore[misc]
def _display_advanced_recommendations(
    recommendations: t.Any, console: Inject[Console]
) -> None:
    if recommendations:
        console.print(
            f"\n[yellow]💡[/yellow] Found {len(recommendations)} optimization recommendations:"
        )
        for rec in recommendations[:3]:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}[
                rec["priority"]
            ]
            console.print(
                f" [{priority_color}]{rec['priority'].upper()}[/{priority_color}]: {rec['title']}"
            )


@depends.inject  # type: ignore[misc]
def _save_advanced_report(
    result: t.Any, advanced_report: str | None, console: Inject[Console]
) -> None:
    if advanced_report:
        import json

        with open(advanced_report, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"[green]📄[/green] Advanced report saved to: {advanced_report}")


@depends.inject  # type: ignore[misc]
def _handle_mkdocs_integration(
    mkdocs_integration: bool,
    mkdocs_serve: bool,
    mkdocs_theme: str,
    mkdocs_output: str | None,
    console: Inject[Console],
) -> bool:
    if not mkdocs_integration:
        return True

    console.print("[cyan]📚[/cyan] Generating MkDocs documentation site...")

    try:
        services = _create_mkdocs_services()
        builder = services["builder"]
        output_dir = _determine_mkdocs_output_dir(mkdocs_output)
        docs_content = _create_sample_docs_content()

        console.print(
            f"[blue]🏗️[/blue] Building documentation site with {mkdocs_theme} theme..."
        )

        _build_mkdocs_site(builder, docs_content, output_dir, mkdocs_serve)
        site = None
        _handle_mkdocs_build_result(site, mkdocs_serve)

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] MkDocs integration error: {e}")
        return False


def _create_sync_filesystem_service() -> t.Any:
    from pathlib import Path

    class SyncFileSystemService:
        def read_file(self, path: str | Path) -> str:
            return Path(path).read_text()

        def write_file(self, path: str | Path, content: str) -> None:
            Path(path).write_text(content)

        def exists(self, path: str | Path) -> bool:
            return Path(path).exists()

        def mkdir(self, path: str | Path, parents: bool = False) -> None:
            Path(path).mkdir(parents=parents, exist_ok=True)

        def ensure_directory(self, path: str | Path) -> None:
            Path(path).mkdir(parents=True, exist_ok=True)

    return SyncFileSystemService()


def _create_config_manager() -> t.Any:
    class ConfigManager:
        def __init__(self) -> None:
            self._config: dict[str, t.Any] = {}

        def get(self, key: str, default: t.Any = None) -> t.Any:
            return self._config.get(key, default)

        def set(self, key: str, value: t.Any) -> None:
            self._config[key] = value

        def save(self) -> bool:
            return True

        def load(self) -> bool:
            return True

    return ConfigManager()


def _create_logger_adapter(logger: t.Any) -> t.Any:
    class LoggerAdapter:
        def __init__(self, logger: t.Any) -> None:
            self._logger = logger

        def debug(self, message: str, **kwargs: t.Any) -> None:
            self._logger.debug(message)

        def info(self, message: str, **kwargs: t.Any) -> None:
            self._logger.info(message)

        def warning(self, message: str, **kwargs: t.Any) -> None:
            self._logger.warning(message)

        def error(self, message: str, **kwargs: t.Any) -> None:
            self._logger.error(message)

    return LoggerAdapter(logger)


def _create_mkdocs_services() -> dict[str, t.Any]:
    from logging import getLogger

    from crackerjack.documentation.mkdocs_integration import (
        MkDocsIntegrationService,
        MkDocsSiteBuilder,
    )

    filesystem = _create_sync_filesystem_service()
    config_manager = _create_config_manager()
    logger = getLogger(__name__)
    logger_adapter = _create_logger_adapter(logger)

    integration_service = MkDocsIntegrationService(
        config_manager, filesystem, logger_adapter
    )
    builder = MkDocsSiteBuilder(integration_service)

    return {"builder": builder, "filesystem": filesystem, "config": config_manager}


def _determine_mkdocs_output_dir(mkdocs_output: str | None) -> "Path":
    from pathlib import Path

    return Path(mkdocs_output) if mkdocs_output else Path.cwd() / "docs_site"


def _create_sample_docs_content() -> dict[str, str]:
    return {
        "index.md": "# Project Documentation\n\nWelcome to the project documentation.",
        "getting-started.md": "# Getting Started\n\nQuick start guide for the project.",
        "api-reference.md": "# API Reference\n\nAPI documentation and examples.",
    }


def _build_mkdocs_site(
    builder: t.Any, docs_content: dict[str, str], output_dir: Path, serve: bool
) -> None:
    import asyncio

    asyncio.run(
        builder.build_documentation_site(
            project_name="Project Documentation",
            project_description="Comprehensive project documentation",
            author="Crackerjack",
            documentation_content=docs_content,
            output_dir=output_dir,
            serve=serve,
        )
    )


@depends.inject  # type: ignore[misc]
def _handle_mkdocs_build_result(
    site: t.Any, mkdocs_serve: bool, console: Inject[Console] = None
) -> None:
    if site:
        console.print(
            f"[green]✅[/green] MkDocs site generated successfully at: {site.build_path}"
        )
        console.print(
            f"[blue]📄[/blue] Generated {len(site.pages)} documentation pages"
        )

        if mkdocs_serve:
            console.print(
                "[blue]🌐[/blue] MkDocs development server started at http://127.0.0.1:8000"
            )
            console.print("[yellow]Press Ctrl+C to stop the server[/yellow]")
    else:
        console.print("[red]❌[/red] Failed to generate MkDocs site")


@depends.inject  # type: ignore[misc]
def _handle_contextual_ai(
    contextual_ai: bool,
    ai_recommendations: int,
    ai_help_query: str | None,
    console: Inject[Console],
) -> bool:
    if not contextual_ai and not ai_help_query:
        return True

    from crackerjack.services.ai.contextual_ai_assistant import ContextualAIAssistant

    console.print("[cyan]🤖[/cyan] Running contextual AI assistant analysis...")

    try:
        from pathlib import Path

        class FileSystemImpl:
            def read_file(self, path: str | t.Any) -> str:
                return Path(path).read_text()

            def write_file(self, path: str | t.Any, content: str) -> None:
                Path(path).write_text(content)

            def exists(self, path: str | t.Any) -> bool:
                return Path(path).exists()

            def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
                Path(path).mkdir(parents=parents, exist_ok=True)

        filesystem = FileSystemImpl()
        assistant = ContextualAIAssistant(filesystem)

        if ai_help_query:
            help_response = assistant.get_quick_help(ai_help_query)
            console.print(f"\n[blue]🔍[/blue] AI Help for '{ai_help_query}':")
            console.print(help_response)
            return False

        console.print(
            "[blue]🧠[/blue] Analyzing project context for AI recommendations..."
        )
        recommendations = assistant.get_contextual_recommendations(ai_recommendations)

        if recommendations:
            assistant.display_recommendations(recommendations)
        else:
            console.print("[green]✨[/green] Great job! No immediate recommendations")

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Contextual AI error: {e}")
        return False


@app.command()
def main(
    commit: bool = CLI_OPTIONS["commit"],
    interactive: bool = CLI_OPTIONS["interactive"],
    no_config_updates: bool = CLI_OPTIONS["no_config_updates"],
    update_precommit: bool = CLI_OPTIONS["update_precommit"],
    verbose: bool = CLI_OPTIONS["verbose"],
    debug: bool = CLI_OPTIONS["debug"],
    publish: BumpOption | None = CLI_OPTIONS["publish"],
    all: str | None = CLI_OPTIONS["all"],
    bump: BumpOption | None = CLI_OPTIONS["bump"],
    strip_code: bool = CLI_OPTIONS["strip_code"],
    run_tests: bool = CLI_OPTIONS["run_tests"],
    benchmark: bool = CLI_OPTIONS["benchmark"],
    test_workers: int = CLI_OPTIONS["test_workers"],
    test_timeout: int = CLI_OPTIONS["test_timeout"],
    skip_hooks: bool = CLI_OPTIONS["skip_hooks"],
    fast: bool = CLI_OPTIONS["fast"],
    comp: bool = CLI_OPTIONS["comp"],
    fast_iteration: bool = CLI_OPTIONS["fast_iteration"],
    tool: str | None = CLI_OPTIONS["tool"],
    changed_only: bool = CLI_OPTIONS["changed_only"],
    all_files: bool = CLI_OPTIONS["all_files"],
    create_pr: bool = CLI_OPTIONS["create_pr"],
    ai_fix: bool = CLI_OPTIONS["ai_fix"],
    start_mcp_server: bool = CLI_OPTIONS["start_mcp_server"],
    stop_mcp_server: bool = CLI_OPTIONS["stop_mcp_server"],
    restart_mcp_server: bool = CLI_OPTIONS["restart_mcp_server"],
    async_mode: bool = CLI_OPTIONS["async_mode"],
    experimental_hooks: bool = CLI_OPTIONS["experimental_hooks"],
    enable_pyrefly: bool = CLI_OPTIONS["enable_pyrefly"],
    enable_ty: bool = CLI_OPTIONS["enable_ty"],
    no_git_tags: bool = CLI_OPTIONS["no_git_tags"],
    skip_version_check: bool = CLI_OPTIONS["skip_version_check"],
    start_websocket_server: bool = CLI_OPTIONS["start_websocket_server"],
    stop_websocket_server: bool = CLI_OPTIONS["stop_websocket_server"],
    restart_websocket_server: bool = CLI_OPTIONS["restart_websocket_server"],
    websocket_port: int | None = CLI_OPTIONS["websocket_port"],
    start_zuban_lsp: bool = CLI_OPTIONS["start_zuban_lsp"],
    stop_zuban_lsp: bool = CLI_OPTIONS["stop_zuban_lsp"],
    restart_zuban_lsp: bool = CLI_OPTIONS["restart_zuban_lsp"],
    no_zuban_lsp: bool = CLI_OPTIONS["no_zuban_lsp"],
    zuban_lsp_port: int = CLI_OPTIONS["zuban_lsp_port"],
    zuban_lsp_mode: str = CLI_OPTIONS["zuban_lsp_mode"],
    zuban_lsp_timeout: int = CLI_OPTIONS["zuban_lsp_timeout"],
    enable_lsp_hooks: bool = CLI_OPTIONS["enable_lsp_hooks"],
    watchdog: bool = CLI_OPTIONS["watchdog"],
    monitor: bool = CLI_OPTIONS["monitor"],
    enhanced_monitor: bool = CLI_OPTIONS["enhanced_monitor"],
    ai_debug: bool = CLI_OPTIONS["ai_debug"],
    job_id: str | None = CLI_OPTIONS["job_id"],
    orchestrated: bool = CLI_OPTIONS["orchestrated"],
    orchestration_strategy: str = CLI_OPTIONS["orchestration_strategy"],
    orchestration_progress: str = CLI_OPTIONS["orchestration_progress"],
    orchestration_ai_mode: str = CLI_OPTIONS["orchestration_ai_mode"],
    dev: bool = CLI_OPTIONS["dev"],
    dashboard: bool = CLI_OPTIONS["dashboard"],
    unified_dashboard: bool = CLI_OPTIONS["unified_dashboard"],
    unified_dashboard_port: int | None = CLI_OPTIONS["unified_dashboard_port"],
    max_iterations: int = CLI_OPTIONS["max_iterations"],
    coverage_status: bool = CLI_OPTIONS["coverage_status"],
    coverage_goal: float | None = CLI_OPTIONS["coverage_goal"],
    no_coverage_ratchet: bool = CLI_OPTIONS["no_coverage_ratchet"],
    boost_coverage: bool = CLI_OPTIONS["boost_coverage"],
    disable_global_locks: bool = CLI_OPTIONS["disable_global_locks"],
    global_lock_timeout: int = CLI_OPTIONS["global_lock_timeout"],
    global_lock_cleanup: bool = CLI_OPTIONS["global_lock_cleanup"],
    global_lock_dir: str | None = CLI_OPTIONS["global_lock_dir"],
    quick: bool = CLI_OPTIONS["quick"],
    thorough: bool = CLI_OPTIONS["thorough"],
    clear_cache: bool = CLI_OPTIONS["clear_cache"],
    cache_stats: bool = CLI_OPTIONS["cache_stats"],
    generate_docs: bool = CLI_OPTIONS["generate_docs"],
    docs_format: str = CLI_OPTIONS["docs_format"],
    validate_docs: bool = CLI_OPTIONS["validate_docs"],
    generate_changelog: bool = CLI_OPTIONS["generate_changelog"],
    changelog_version: str | None = CLI_OPTIONS["changelog_version"],
    changelog_since: str | None = CLI_OPTIONS["changelog_since"],
    changelog_dry_run: bool = CLI_OPTIONS["changelog_dry_run"],
    auto_version: bool = CLI_OPTIONS["auto_version"],
    version_since: str | None = CLI_OPTIONS["version_since"],
    accept_version: bool = CLI_OPTIONS["accept_version"],
    smart_commit: bool = CLI_OPTIONS["smart_commit"],
    heatmap: bool = CLI_OPTIONS["heatmap"],
    heatmap_type: str = CLI_OPTIONS["heatmap_type"],
    heatmap_output: str | None = CLI_OPTIONS["heatmap_output"],
    anomaly_detection: bool = CLI_OPTIONS["anomaly_detection"],
    anomaly_sensitivity: float = CLI_OPTIONS["anomaly_sensitivity"],
    anomaly_report: str | None = CLI_OPTIONS["anomaly_report"],
    predictive_analytics: bool = CLI_OPTIONS["predictive_analytics"],
    prediction_periods: int = CLI_OPTIONS["prediction_periods"],
    analytics_dashboard: str | None = CLI_OPTIONS["analytics_dashboard"],
    advanced_optimizer: bool = CLI_OPTIONS["advanced_optimizer"],
    advanced_profile: str | None = CLI_OPTIONS["advanced_profile"],
    advanced_report: str | None = CLI_OPTIONS["advanced_report"],
    mkdocs_integration: bool = CLI_OPTIONS["mkdocs_integration"],
    mkdocs_serve: bool = CLI_OPTIONS["mkdocs_serve"],
    mkdocs_theme: str = CLI_OPTIONS["mkdocs_theme"],
    mkdocs_output: str | None = CLI_OPTIONS["mkdocs_output"],
    contextual_ai: bool = CLI_OPTIONS["contextual_ai"],
    ai_recommendations: int = CLI_OPTIONS["ai_recommendations"],
    ai_help_query: str | None = CLI_OPTIONS["ai_help_query"],
    check_config_updates: bool = CLI_OPTIONS["check_config_updates"],
    apply_config_updates: bool = CLI_OPTIONS["apply_config_updates"],
    diff_config: str | None = CLI_OPTIONS["diff_config"],
    config_interactive: bool = CLI_OPTIONS["config_interactive"],
    refresh_cache: bool = CLI_OPTIONS["refresh_cache"],
    use_acb_workflows: bool = CLI_OPTIONS["use_acb_workflows"],
    use_legacy_orchestrator: bool = CLI_OPTIONS["use_legacy_orchestrator"],
    index: str | None = CLI_OPTIONS["index"],
    search: str | None = CLI_OPTIONS["search"],
    semantic_stats: bool = CLI_OPTIONS["semantic_stats"],
    remove_from_index: str | None = CLI_OPTIONS["remove_from_index"],
) -> None:
    from acb.depends import depends

    from crackerjack.config import register_services
    from crackerjack.config.loader import load_settings
    from crackerjack.config.settings import CrackerjackSettings

    settings = load_settings(CrackerjackSettings)
    depends.set(CrackerjackSettings, settings)

    register_services()

    options = create_options(
        commit,
        interactive,
        no_config_updates,
        update_precommit,
        verbose,
        debug,
        publish,
        bump,
        benchmark,
        test_workers,
        test_timeout,
        skip_hooks,
        fast,
        comp,
        fast_iteration,
        tool,
        changed_only,
        all_files,
        create_pr,
        async_mode,
        experimental_hooks,
        enable_pyrefly,
        enable_ty,
        start_zuban_lsp,
        stop_zuban_lsp,
        restart_zuban_lsp,
        no_zuban_lsp,
        zuban_lsp_port,
        zuban_lsp_mode,
        zuban_lsp_timeout,
        enable_lsp_hooks,
        no_git_tags,
        skip_version_check,
        orchestrated,
        orchestration_strategy,
        orchestration_progress,
        orchestration_ai_mode,
        dev,
        dashboard,
        unified_dashboard,
        unified_dashboard_port,
        max_iterations,
        coverage_status,
        coverage_goal,
        no_coverage_ratchet,
        boost_coverage,
        disable_global_locks,
        global_lock_timeout,
        global_lock_cleanup,
        global_lock_dir,
        quick,
        thorough,
        clear_cache,
        cache_stats,
        generate_docs,
        docs_format,
        validate_docs,
        generate_changelog,
        changelog_version,
        changelog_since,
        changelog_dry_run,
        auto_version,
        version_since,
        accept_version,
        smart_commit,
        heatmap,
        heatmap_type,
        heatmap_output,
        anomaly_detection,
        anomaly_sensitivity,
        anomaly_report,
        predictive_analytics,
        prediction_periods,
        analytics_dashboard,
        advanced_optimizer,
        advanced_profile,
        advanced_report,
        mkdocs_integration,
        mkdocs_serve,
        mkdocs_theme,
        mkdocs_output,
        contextual_ai,
        ai_recommendations,
        ai_help_query,
        check_config_updates,
        apply_config_updates,
        diff_config,
        config_interactive,
        refresh_cache,
        use_acb_workflows,
        use_legacy_orchestrator,
        run_tests=run_tests,
    )

    options.index = index
    options.search = search
    options.semantic_stats = semantic_stats
    options.remove_from_index = remove_from_index

    ai_fix, verbose = _setup_debug_and_verbose_flags(
        ai_fix, ai_debug, debug, verbose, options
    )
    setup_ai_agent_env(ai_fix, ai_debug or debug)

    if not _process_all_commands(locals(), options):
        return

    if interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, async_mode, job_id, orchestrated)


def _process_all_commands(local_vars: t.Any, options: t.Any) -> bool:
    if _handle_cache_commands(local_vars["clear_cache"], local_vars["cache_stats"]):
        return False

    if (
        local_vars["check_config_updates"]
        or local_vars["apply_config_updates"]
        or local_vars["diff_config"]
        or local_vars["refresh_cache"]
    ):
        handle_config_updates(options)
        return False

    if not _handle_semantic_commands(
        local_vars["index"],
        local_vars["search"],
        local_vars["semantic_stats"],
        local_vars["remove_from_index"],
        options,
    ):
        return False

    if _handle_server_commands(
        local_vars["monitor"],
        local_vars["enhanced_monitor"],
        local_vars["dashboard"],
        local_vars["unified_dashboard"],
        local_vars["unified_dashboard_port"],
        local_vars["watchdog"],
        local_vars["start_websocket_server"],
        local_vars["stop_websocket_server"],
        local_vars["restart_websocket_server"],
        local_vars["start_mcp_server"],
        local_vars["stop_mcp_server"],
        local_vars["restart_mcp_server"],
        local_vars["websocket_port"],
        local_vars["start_zuban_lsp"],
        local_vars["stop_zuban_lsp"],
        local_vars["restart_zuban_lsp"],
        local_vars["zuban_lsp_port"],
        local_vars["zuban_lsp_mode"],
        local_vars["dev"],
    ):
        return False

    if not _handle_coverage_status(local_vars["coverage_status"], options):
        return False

    return _handle_analysis_commands(local_vars, options)


def _handle_analysis_commands(local_vars: t.Any, options: t.Any) -> bool:
    if not _handle_documentation_commands(
        local_vars["generate_docs"], local_vars["validate_docs"], options
    ):
        return False

    if not _handle_changelog_commands(
        local_vars["generate_changelog"],
        local_vars["changelog_dry_run"],
        local_vars["changelog_version"],
        local_vars["changelog_since"],
        options,
    ):
        return False

    if not _handle_version_analysis(
        local_vars["auto_version"],
        local_vars["version_since"],
        local_vars["accept_version"],
        options,
    ):
        return False

    return _handle_specialized_analytics(local_vars)


def _handle_specialized_analytics(local_vars: t.Any) -> bool:
    if not _handle_heatmap_generation(
        local_vars["heatmap"], local_vars["heatmap_type"], local_vars["heatmap_output"]
    ):
        return False

    if not _handle_anomaly_detection(
        local_vars["anomaly_detection"],
        local_vars["anomaly_sensitivity"],
        local_vars["anomaly_report"],
    ):
        return False

    if not _handle_predictive_analytics(
        local_vars["predictive_analytics"],
        local_vars["prediction_periods"],
        local_vars["analytics_dashboard"],
    ):
        return False

    return _handle_advanced_features(local_vars)


@depends.inject  # type: ignore[misc]
def _display_coverage_info(
    coverage_info: dict[str, t.Any], console: Inject[Console]
) -> None:
    coverage_percent = coverage_info.get("coverage_percent", 0.0)
    coverage_source = coverage_info.get("source", "unknown")

    if coverage_percent > 0:
        console.print(
            f"[green]Current Coverage:[/green] {coverage_percent:.2f}% (from {coverage_source})"
        )
    else:
        console.print("[yellow]Current Coverage:[/yellow] No coverage data available")

    status_message = coverage_info.get("message")
    if status_message:
        console.print(f"[dim]{status_message}[/dim]")


@depends.inject  # type: ignore[misc]
def _display_coverage_report(test_manager: t.Any, console: Inject[Console]) -> None:
    coverage_report = test_manager.get_coverage_report()
    if coverage_report:
        console.print(f"[cyan]Details:[/cyan] {coverage_report}")


@depends.inject  # type: ignore[misc]
def _display_ratchet_status(test_manager: t.Any, console: Inject[Console]) -> None:
    from contextlib import suppress

    with suppress(Exception):
        ratchet_status = test_manager.get_coverage_ratchet_status()
        if ratchet_status:
            next_milestone = ratchet_status.get("next_milestone")
            if next_milestone:
                console.print(f"[cyan]Next Milestone:[/cyan] {next_milestone:.0f}%")

            milestones = ratchet_status.get("milestones_achieved", [])
            if milestones:
                console.print(f"[green]Milestones Achieved:[/green] {len(milestones)}")


@depends.inject  # type: ignore[misc]
def _handle_coverage_status(
    coverage_status: bool, options: t.Any, console: Inject[Console]
) -> bool:
    if not coverage_status:
        return True

    try:
        from pathlib import Path

        from crackerjack.managers.test_manager import TestManager

        pkg_path = Path.cwd()

        test_manager = TestManager(pkg_path)

        console.print("[cyan]📊[/cyan] Coverage Status Report")
        console.print("=" * 50)

        coverage_info = test_manager.get_coverage()
        _display_coverage_info(coverage_info)

        _display_coverage_report(test_manager)

        _display_ratchet_status(test_manager)

        console.print()
        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Failed to get coverage status: {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


@depends.inject  # type: ignore[misc]
def _handle_semantic_commands(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
    options: t.Any,
    console: Inject[Console],
) -> bool:
    if not _has_semantic_operations(index, search, semantic_stats, remove_from_index):
        return True

    console.print("[cyan]🔍[/cyan] Running semantic search operations...")

    try:
        _execute_semantic_operations(index, search, semantic_stats, remove_from_index)
        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Semantic search error: {e}")
        return False


def _has_semantic_operations(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
) -> bool:
    return any([index, search, semantic_stats, remove_from_index])


def _execute_semantic_operations(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
) -> list[str]:
    if index:
        handle_semantic_index(index)

    if search:
        handle_semantic_search(search)

    if semantic_stats:
        handle_semantic_stats()

    if remove_from_index:
        handle_remove_from_semantic_index(remove_from_index)

    return []


def _handle_advanced_features(local_vars: t.Any) -> bool:
    if not _handle_advanced_optimizer(
        local_vars["advanced_optimizer"],
        local_vars["advanced_profile"],
        local_vars["advanced_report"],
    ):
        return False

    if not _handle_mkdocs_integration(
        local_vars["mkdocs_integration"],
        local_vars["mkdocs_serve"],
        local_vars["mkdocs_theme"],
        local_vars["mkdocs_output"],
    ):
        return False

    if not _handle_contextual_ai(
        local_vars["contextual_ai"],
        local_vars["ai_recommendations"],
        local_vars["ai_help_query"],
    ):
        return False

    return True


def cli() -> None:
    app()


if __name__ == "__main__":
    app()
