#!/usr/bin/env python3
"""Application-Aware Context Monitoring for Session Management MCP Server.

Monitors IDE activity and browser documentation to enrich session context.
Excludes Slack/Discord as per Phase 4 requirements.
"""

import asyncio
import contextlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Create stub for FileSystemEventHandler when watchdog is not available
    class FileSystemEventHandler:
        pass


try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class ActivityEvent:
    """Represents a monitored activity event."""

    timestamp: str
    event_type: str  # 'file_change', 'app_focus', 'browser_nav'
    application: str
    details: dict[str, Any]
    project_path: str | None = None
    relevance_score: float = 0.0


class IDEActivityMonitor:
    """Monitors IDE file changes and activity."""

    def __init__(self, project_paths: list[str]) -> None:
        self.project_paths = project_paths
        self.observers = []
        self.activity_buffer = []
        self.last_activity = {}
        self.ide_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".rs",
            ".go",
            ".php",
            ".rb",
            ".swift",
            ".kt",
            ".scala",
            ".cs",
            ".html",
            ".css",
            ".scss",
            ".vue",
            ".svelte",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".md",
            ".txt",
            ".sql",
            ".sh",
            ".bat",
        }

    def start_monitoring(self):
        """Start file system monitoring."""
        if not WATCHDOG_AVAILABLE:
            return False

        for path in self.project_paths:
            if Path(path).exists():
                event_handler = IDEFileHandler(self)
                observer = Observer()
                observer.schedule(event_handler, path, recursive=True)
                observer.start()
                self.observers.append(observer)

        return len(self.observers) > 0

    def stop_monitoring(self) -> None:
        """Stop file system monitoring."""
        for observer in self.observers:
            observer.stop()
            observer.join()
        self.observers.clear()

    def add_activity(self, event: ActivityEvent) -> None:
        """Add activity event to buffer."""
        self.activity_buffer.append(event)

        # Keep buffer size manageable
        if len(self.activity_buffer) > 1000:
            self.activity_buffer = self.activity_buffer[-500:]

    def get_recent_activity(self, minutes: int = 30) -> list[ActivityEvent]:
        """Get recent activity within specified minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat()

        return [
            event for event in self.activity_buffer if event.timestamp >= cutoff_str
        ]

    def get_active_files(self, minutes: int = 60) -> list[dict[str, Any]]:
        """Get files actively being worked on."""
        recent_events = self.get_recent_activity(minutes)
        file_activity = defaultdict(list)

        for event in recent_events:
            if event.event_type == "file_change" and "file_path" in event.details:
                file_path = event.details["file_path"]
                file_activity[file_path].append(event)

        # Score files by activity frequency and recency
        active_files = []
        for file_path, events in file_activity.items():
            score = len(events)
            latest_event = max(events, key=lambda e: e.timestamp)

            # Boost score for recent activity
            time_diff = datetime.now() - datetime.fromisoformat(latest_event.timestamp)
            if time_diff.total_seconds() < 300:  # 5 minutes
                score *= 2

            active_files.append(
                {
                    "file_path": file_path,
                    "activity_score": score,
                    "event_count": len(events),
                    "last_activity": latest_event.timestamp,
                    "project_path": latest_event.project_path,
                },
            )

        return sorted(active_files, key=lambda x: x["activity_score"], reverse=True)


class IDEFileHandler(FileSystemEventHandler):
    """Handles file system events for IDE monitoring."""

    def __init__(self, monitor: IDEActivityMonitor) -> None:
        self.monitor = monitor
        self.ignore_patterns = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "dist",
            "build",
            ".DS_Store",
            ".idea",
            ".vscode/settings.json",
        }

    def should_ignore(self, file_path: str) -> bool:
        """Check if file should be ignored."""
        path = Path(file_path)

        # Check ignore patterns
        for part in path.parts:
            if part in self.ignore_patterns:
                return True

        # Check if it's a relevant file extension
        if path.suffix not in self.monitor.ide_extensions:
            return True

        # Ignore temporary files
        return bool(path.name.startswith(".") or path.name.endswith("~"))

    def on_modified(self, event) -> None:
        if event.is_directory or self.should_ignore(event.src_path):
            return

        # Determine project path
        project_path = None
        src_path = Path(event.src_path)
        for proj_path in self.monitor.project_paths:
            if src_path.is_relative_to(proj_path):
                project_path = proj_path
                break

        activity_event = ActivityEvent(
            timestamp=datetime.now().isoformat(),
            event_type="file_change",
            application="ide",
            details={
                "file_path": event.src_path,
                "file_name": src_path.name,
                "file_extension": src_path.suffix,
                "change_type": "modified",
            },
            project_path=project_path,
            relevance_score=0.8,
        )

        self.monitor.add_activity(activity_event)


class BrowserDocumentationMonitor:
    """Monitors browser activity for documentation sites."""

    def __init__(self) -> None:
        self.doc_domains = {
            "docs.python.org",
            "developer.mozilla.org",
            "docs.rs",
            "docs.oracle.com",
            "docs.microsoft.com",
            "docs.aws.amazon.com",
            "cloud.google.com",
            "docs.github.com",
            "docs.gitlab.com",
            "stackoverflow.com",
            "github.com",
            "fastapi.tiangolo.com",
            "pydantic-docs.helpmanual.io",
            "django-documentation",
            "flask.palletsprojects.com",
            "nodejs.org",
            "reactjs.org",
            "vuejs.org",
            "angular.io",
            "svelte.dev",
        }
        self.activity_buffer = []
        self.browser_processes = set()

    def get_browser_processes(self) -> list[dict[str, Any]]:
        """Get currently running browser processes."""
        if not PSUTIL_AVAILABLE:
            return []

        browsers = []
        browser_names = {"chrome", "firefox", "safari", "edge", "brave"}

        try:
            for proc in psutil.process_iter(["pid", "name", "create_time"]):
                proc_name = proc.info["name"].lower()
                if any(browser in proc_name for browser in browser_names):
                    browsers.append(
                        {
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "create_time": proc.info["create_time"],
                        },
                    )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return browsers

    def extract_documentation_context(self, url: str) -> dict[str, Any]:
        """Extract context from documentation URLs."""
        context = {"domain": "", "technology": "", "topic": "", "relevance": 0.0}

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc
            path = parsed.path

            context["domain"] = domain

            # Determine technology and relevance
            if "python" in domain or "python" in path:
                context["technology"] = "python"
                context["relevance"] = 0.9
            elif (
                "javascript" in path
                or "js" in path
                or domain in ["developer.mozilla.org", "nodejs.org"]
            ):
                context["technology"] = "javascript"
                context["relevance"] = 0.8
            elif "rust" in domain or "docs.rs" in domain:
                context["technology"] = "rust"
                context["relevance"] = 0.8
            elif any(
                framework in domain for framework in ["django", "flask", "fastapi"]
            ):
                context["technology"] = "python-web"
                context["relevance"] = 0.9
            elif any(
                framework in domain
                for framework in ["react", "vue", "angular", "svelte"]
            ):
                context["technology"] = "frontend"
                context["relevance"] = 0.8

            # Extract topic from path
            path_parts = [p for p in path.split("/") if p]
            if path_parts:
                context["topic"] = (
                    path_parts[-1]
                    if path_parts[-1] != "index.html"
                    else path_parts[-2]
                    if len(path_parts) > 1
                    else ""
                )

        except Exception:
            pass

        return context

    def add_browser_activity(self, url: str, title: str = "") -> None:
        """Add browser navigation activity."""
        context = self.extract_documentation_context(url)

        activity_event = ActivityEvent(
            timestamp=datetime.now().isoformat(),
            event_type="browser_nav",
            application="browser",
            details={
                "url": url,
                "title": title,
                "domain": context["domain"],
                "technology": context["technology"],
                "topic": context["topic"],
            },
            relevance_score=context["relevance"],
        )

        self.activity_buffer.append(activity_event)

        # Keep buffer manageable
        if len(self.activity_buffer) > 500:
            self.activity_buffer = self.activity_buffer[-250:]


class ApplicationFocusMonitor:
    """Monitors application focus changes."""

    def __init__(self) -> None:
        self.focus_history = []
        self.current_app = None
        self.app_categories = {
            "ide": {
                "code",
                "pycharm",
                "vscode",
                "sublime",
                "atom",
                "vim",
                "emacs",
                "intellij",
            },
            "browser": {"chrome", "firefox", "safari", "edge", "brave"},
            "terminal": {
                "terminal",
                "term",
                "console",
                "cmd",
                "powershell",
                "zsh",
                "bash",
            },
            "documentation": {"devdocs", "dash", "zeal"},
        }

    def get_focused_application(self) -> dict[str, Any] | None:
        """Get currently focused application."""
        if not PSUTIL_AVAILABLE:
            return None

        try:
            # This is a simplified version - would need platform-specific implementation
            # for full window focus detection
            for proc in psutil.process_iter(["pid", "name"]):
                proc_name = proc.info["name"].lower()
                category = self._categorize_app(proc_name)
                if category:
                    return {
                        "name": proc.info["name"],
                        "category": category,
                        "pid": proc.info["pid"],
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return None

    def _categorize_app(self, app_name: str) -> str | None:
        """Categorize application by name."""
        for category, keywords in self.app_categories.items():
            if any(keyword in app_name for keyword in keywords):
                return category
        return None

    def add_focus_event(self, app_info: dict[str, Any]) -> None:
        """Add application focus event."""
        activity_event = ActivityEvent(
            timestamp=datetime.now().isoformat(),
            event_type="app_focus",
            application=app_info["name"],
            details={"category": app_info["category"], "pid": app_info["pid"]},
            relevance_score=0.6 if app_info["category"] in ["ide", "terminal"] else 0.3,
        )

        self.focus_history.append(activity_event)

        # Keep history manageable
        if len(self.focus_history) > 200:
            self.focus_history = self.focus_history[-100:]


class ActivityDatabase:
    """SQLite database for storing activity events."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    application TEXT NOT NULL,
                    details TEXT NOT NULL,
                    project_path TEXT,
                    relevance_score REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON activity_events(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type ON activity_events(event_type)
            """)

    def store_event(self, event: ActivityEvent) -> None:
        """Store activity event in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO activity_events
                (timestamp, event_type, application, details, project_path, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    event.timestamp,
                    event.event_type,
                    event.application,
                    json.dumps(event.details),
                    event.project_path,
                    event.relevance_score,
                ),
            )

    def get_events(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        event_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[ActivityEvent]:
        """Retrieve activity events from database."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM activity_events WHERE 1=1"
            params = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)

            if event_types:
                placeholders = ",".join("?" * len(event_types))
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            events = []
            for row in rows:
                events.append(
                    ActivityEvent(
                        timestamp=row[1],
                        event_type=row[2],
                        application=row[3],
                        details=json.loads(row[4]),
                        project_path=row[5],
                        relevance_score=row[6] or 0.0,
                    ),
                )

            return events

    def cleanup_old_events(self, days_to_keep: int = 30):
        """Remove old activity events."""
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        cutoff_str = cutoff.isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM activity_events WHERE timestamp < ?",
                (cutoff_str,),
            )
            return cursor.rowcount


class ApplicationMonitor:
    """Main application monitoring coordinator."""

    def __init__(self, data_dir: str, project_paths: list[str] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.project_paths = project_paths or []
        self.db = ActivityDatabase(str(self.data_dir / "activity.db"))

        self.ide_monitor = IDEActivityMonitor(self.project_paths)
        self.browser_monitor = BrowserDocumentationMonitor()
        self.focus_monitor = ApplicationFocusMonitor()

        self.monitoring_active = False
        self._monitoring_task = None

    async def start_monitoring(self):
        """Start all monitoring components."""
        if self.monitoring_active:
            return None

        self.monitoring_active = True

        # Start IDE monitoring
        ide_started = self.ide_monitor.start_monitoring()

        # Start background monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        return {
            "ide_monitoring": ide_started,
            "watchdog_available": WATCHDOG_AVAILABLE,
            "psutil_available": PSUTIL_AVAILABLE,
            "project_paths": self.project_paths,
        }

    async def stop_monitoring(self) -> None:
        """Stop all monitoring."""
        self.monitoring_active = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task

        self.ide_monitor.stop_monitoring()

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Check application focus
                focused_app = self.focus_monitor.get_focused_application()
                if focused_app and focused_app != self.focus_monitor.current_app:
                    self.focus_monitor.add_focus_event(focused_app)
                    self.focus_monitor.current_app = focused_app

                # Persist buffered IDE events
                for event in self.ide_monitor.activity_buffer[-10:]:  # Last 10 events
                    self.db.store_event(event)

                # Persist buffered browser events
                for event in self.browser_monitor.activity_buffer[-10:]:
                    self.db.store_event(event)

                # Persist focus events
                for event in self.focus_monitor.focus_history[-5:]:
                    self.db.store_event(event)

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue monitoring
                print(f"Monitoring error: {e}")
                await asyncio.sleep(60)

    def get_activity_summary(self, hours: int = 2) -> dict[str, Any]:
        """Get activity summary for specified hours."""
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        events = self.db.get_events(start_time=start_time, limit=500)

        summary = {
            "total_events": len(events),
            "time_range_hours": hours,
            "event_types": defaultdict(int),
            "applications": defaultdict(int),
            "active_files": [],
            "documentation_sites": [],
            "average_relevance": 0.0,
        }

        total_relevance = 0
        doc_sites = set()

        for event in events:
            summary["event_types"][event.event_type] += 1
            summary["applications"][event.application] += 1
            total_relevance += event.relevance_score

            if event.event_type == "browser_nav" and event.details.get("domain"):
                doc_sites.add(event.details["domain"])

        if events:
            summary["average_relevance"] = total_relevance / len(events)

        summary["active_files"] = self.ide_monitor.get_active_files(hours * 60)
        summary["documentation_sites"] = list(doc_sites)

        # Convert defaultdict to regular dict for JSON serialization
        summary["event_types"] = dict(summary["event_types"])
        summary["applications"] = dict(summary["applications"])

        return summary

    def get_context_insights(self, hours: int = 1) -> dict[str, Any]:
        """Get contextual insights from recent activity."""
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        events = self.db.get_events(start_time=start_time, limit=200)

        insights = {
            "primary_focus": None,
            "technologies_used": set(),
            "active_projects": set(),
            "documentation_topics": [],
            "productivity_score": 0.0,
            "context_switches": 0,
        }

        if not events:
            return insights

        # Analyze primary focus
        app_time = defaultdict(int)
        last_app = None

        for event in events:
            app_time[event.application] += 1

            # Count context switches
            if last_app and last_app != event.application:
                insights["context_switches"] += 1
            last_app = event.application

            # Extract technologies
            if event.event_type == "file_change":
                ext = event.details.get("file_extension", "")
                if ext == ".py":
                    insights["technologies_used"].add("python")
                elif ext in [".js", ".ts"]:
                    insights["technologies_used"].add("javascript")
                elif ext == ".rs":
                    insights["technologies_used"].add("rust")

            # Extract projects
            if event.project_path:
                insights["active_projects"].add(event.project_path)

            # Extract documentation topics
            if event.event_type == "browser_nav":
                topic = event.details.get("topic")
                technology = event.details.get("technology")
                if topic and technology:
                    insights["documentation_topics"].append(f"{technology}: {topic}")

        # Determine primary focus
        if app_time:
            insights["primary_focus"] = max(app_time.items(), key=lambda x: x[1])[0]

        # Calculate productivity score based on relevant activity
        relevant_events = [e for e in events if e.relevance_score > 0.5]
        if events:
            insights["productivity_score"] = len(relevant_events) / len(events)

        # Convert sets to lists for JSON serialization
        insights["technologies_used"] = list(insights["technologies_used"])
        insights["active_projects"] = list(insights["active_projects"])

        return insights
