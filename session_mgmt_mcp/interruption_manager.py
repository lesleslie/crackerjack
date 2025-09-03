"""Smart Interruption Management module for context switch detection and auto-save.

This module provides intelligent interruption handling including:
- Context switch detection (app/window changes)
- Automatic session state preservation
- Smart recovery from interruptions
- Focus tracking and restoration
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

try:
    import gzip
    import pickle

    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False

logger = logging.getLogger(__name__)


class InterruptionType(Enum):
    """Types of interruptions detected."""

    APP_SWITCH = "app_switch"
    WINDOW_CHANGE = "window_change"
    SYSTEM_IDLE = "system_idle"
    FOCUS_LOST = "focus_lost"
    FILE_CHANGE = "file_change"
    PROCESS_CHANGE = "process_change"
    MANUAL_SAVE = "manual_save"


class ContextState(Enum):
    """Context preservation states."""

    ACTIVE = "active"
    INTERRUPTED = "interrupted"
    PRESERVED = "preserved"
    RESTORED = "restored"
    LOST = "lost"


@dataclass
class InterruptionEvent:
    """Interruption event with context information."""

    id: str
    event_type: InterruptionType
    timestamp: datetime
    source_context: dict[str, Any]
    target_context: dict[str, Any]
    duration: float | None
    recovery_data: dict[str, Any] | None
    auto_saved: bool
    user_id: str
    project_id: str | None


@dataclass
class SessionContext:
    """Current session context information."""

    session_id: str
    user_id: str
    project_id: str | None
    active_app: str | None
    active_window: str | None
    working_directory: str
    open_files: list[str]
    cursor_positions: dict[str, Any]
    environment_vars: dict[str, str]
    process_state: dict[str, Any]
    last_activity: datetime
    focus_duration: float
    interruption_count: int
    recovery_attempts: int


class FocusTracker:
    """Tracks application and window focus changes."""

    def __init__(self, callback: Callable | None = None) -> None:
        """Initialize focus tracker."""
        self.callback = callback
        self.current_app = None
        self.current_window = None
        self.last_check = time.time()
        self.focus_start = time.time()
        self.running = False
        self._monitor_thread = None

    def start_monitoring(self) -> None:
        """Start focus monitoring."""
        if self.running:
            return

        self.running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop focus monitoring."""
        self.running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)

    def _monitor_loop(self) -> None:
        """Focus monitoring loop."""
        while self.running:
            try:
                self._check_focus_change()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                logger.exception(f"Focus monitoring error: {e}")
                time.sleep(5.0)  # Wait longer on error

    def _check_focus_change(self) -> None:
        """Check for focus changes using cross-platform methods."""
        try:
            current_app = self._get_active_application()
            current_window = self._get_active_window()

            now = time.time()

            # Detect app switch
            if current_app != self.current_app:
                focus_duration = now - self.focus_start

                if self.callback and self.current_app:
                    self.callback(
                        {
                            "type": InterruptionType.APP_SWITCH,
                            "source_app": self.current_app,
                            "target_app": current_app,
                            "focus_duration": focus_duration,
                            "timestamp": datetime.now(),
                        },
                    )

                self.current_app = current_app
                self.focus_start = now

            # Detect window change within same app
            elif current_window != self.current_window:
                focus_duration = now - self.focus_start

                if self.callback and self.current_window:
                    self.callback(
                        {
                            "type": InterruptionType.WINDOW_CHANGE,
                            "source_window": self.current_window,
                            "target_window": current_window,
                            "app": current_app,
                            "focus_duration": focus_duration,
                            "timestamp": datetime.now(),
                        },
                    )

                self.current_window = current_window
                self.focus_start = now

            self.last_check = now

        except Exception as e:
            logger.debug(f"Focus check failed: {e}")

    def _get_active_application(self) -> str | None:
        """Get currently active application name."""
        if not PSUTIL_AVAILABLE:
            return None

        try:
            # Try to get the foreground process
            # This is a simplified cross-platform approach
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    # Basic heuristic: look for common GUI applications
                    name = proc.info["name"]
                    if any(
                        gui_hint in name.lower()
                        for gui_hint in ["code", "browser", "terminal", "editor", "ide"]
                    ):
                        return name
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return "Unknown"

        except Exception:
            return None

    def _get_active_window(self) -> str | None:
        """Get currently active window title."""
        # This would require platform-specific implementations
        # For now, return a placeholder
        return f"Window_{int(time.time() % 1000)}"


class FileChangeHandler(FileSystemEventHandler):
    """Handles file system change events."""

    def __init__(self, callback: Callable | None = None) -> None:
        """Initialize file change handler."""
        super().__init__()
        self.callback = callback
        self.last_events = {}
        self.debounce_time = 1.0  # Seconds

    def on_modified(self, event) -> None:
        """Handle file modification."""
        if event.is_directory:
            return

        now = time.time()
        file_path = event.src_path

        # Debounce rapid changes
        if file_path in self.last_events:
            if now - self.last_events[file_path] < self.debounce_time:
                return

        self.last_events[file_path] = now

        if self.callback:
            self.callback(
                {
                    "type": InterruptionType.FILE_CHANGE,
                    "file_path": file_path,
                    "event_type": "modified",
                    "timestamp": datetime.now(),
                },
            )

    def on_created(self, event) -> None:
        """Handle file creation."""
        if event.is_directory:
            return

        if self.callback:
            self.callback(
                {
                    "type": InterruptionType.FILE_CHANGE,
                    "file_path": event.src_path,
                    "event_type": "created",
                    "timestamp": datetime.now(),
                },
            )

    def on_deleted(self, event) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return

        if self.callback:
            self.callback(
                {
                    "type": InterruptionType.FILE_CHANGE,
                    "file_path": event.src_path,
                    "event_type": "deleted",
                    "timestamp": datetime.now(),
                },
            )


class InterruptionManager:
    """Manages interruption detection and context preservation."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize interruption manager."""
        self.db_path = db_path or str(
            Path.home() / ".claude" / "data" / "interruption_manager.db",
        )
        self._lock = threading.Lock()
        self.current_context: SessionContext | None = None
        self.focus_tracker = FocusTracker(callback=self._handle_interruption)
        self.file_observer: Observer | None = None
        self.file_handler = FileChangeHandler(callback=self._handle_interruption)
        self.auto_save_enabled = True
        self.save_threshold = 30.0  # Auto-save after 30 seconds of focus
        self.idle_threshold = 300.0  # 5 minutes idle detection
        self._preservation_callbacks: list[Callable] = []
        self._restoration_callbacks: list[Callable] = []
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for interruption tracking."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interruption_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    source_context TEXT,  -- JSON
                    target_context TEXT,  -- JSON
                    duration REAL,
                    recovery_data TEXT,   -- JSON
                    auto_saved BOOLEAN,
                    user_id TEXT NOT NULL,
                    project_id TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_contexts (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project_id TEXT,
                    context_data TEXT,    -- JSON
                    state TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    preserved_at TIMESTAMP,
                    restore_count INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_snapshots (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    data BLOB,  -- Compressed context data
                    metadata TEXT  -- JSON
                )
            """)

            # Create indices
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interruptions_timestamp ON interruption_events(timestamp)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_interruptions_user ON interruption_events(user_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_contexts_user ON session_contexts(user_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_contexts_state ON session_contexts(state)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_session ON context_snapshots(session_id)",
            )

    def start_monitoring(
        self, working_directory: str = ".", watch_files: bool = True
    ) -> None:
        """Start interruption monitoring."""
        # Start focus tracking
        self.focus_tracker.start_monitoring()

        # Start file watching if requested
        if watch_files and WATCHDOG_AVAILABLE:
            try:
                self.file_observer = Observer()
                self.file_observer.schedule(
                    self.file_handler,
                    working_directory,
                    recursive=True,
                )
                self.file_observer.start()
            except Exception as e:
                logger.warning(f"Failed to start file monitoring: {e}")

    def stop_monitoring(self) -> None:
        """Stop interruption monitoring."""
        # Stop focus tracking
        self.focus_tracker.stop_monitoring()

        # Stop file watching
        if self.file_observer:
            try:
                self.file_observer.stop()
                self.file_observer.join(timeout=2.0)
            except Exception as e:
                logger.warning(f"Error stopping file observer: {e}")
            finally:
                self.file_observer = None

    async def create_session_context(
        self,
        user_id: str,
        project_id: str | None = None,
        working_directory: str = ".",
    ) -> str:
        """Create new session context."""
        session_id = f"ctx_{int(time.time() * 1000)}"

        context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            active_app=self.focus_tracker.current_app,
            active_window=self.focus_tracker.current_window,
            working_directory=working_directory,
            open_files=[],
            cursor_positions={},
            environment_vars=dict(os.environ) if "os" in globals() else {},
            process_state={},
            last_activity=datetime.now(),
            focus_duration=0.0,
            interruption_count=0,
            recovery_attempts=0,
        )

        self.current_context = context

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO session_contexts (session_id, user_id, project_id, context_data, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    user_id,
                    project_id,
                    json.dumps(asdict(context)),
                    ContextState.ACTIVE.value,
                    datetime.now(),
                    datetime.now(),
                ),
            )

        return session_id

    async def preserve_context(
        self,
        session_id: str | None = None,
        force: bool = False,
    ) -> bool:
        """Preserve current session context."""
        context = self.current_context
        if not context:
            return False

        session_id = session_id or context.session_id

        try:
            # Create context snapshot
            snapshot_data = {
                "context": asdict(context),
                "timestamp": datetime.now().isoformat(),
                "preservation_reason": "manual" if force else "auto",
                "environment": self._capture_environment_state(),
            }

            # Compress the data
            compressed_data = None
            if COMPRESSION_AVAILABLE:
                try:
                    serialized = pickle.dumps(snapshot_data)
                    compressed_data = gzip.compress(serialized)
                except Exception as e:
                    logger.warning(f"Compression failed: {e}")
                    compressed_data = json.dumps(snapshot_data).encode()
            else:
                compressed_data = json.dumps(snapshot_data).encode()

            snapshot_id = f"snap_{int(time.time() * 1000)}"

            # Store snapshot
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO context_snapshots (id, session_id, snapshot_type, timestamp, data, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        snapshot_id,
                        session_id,
                        "preservation",
                        datetime.now(),
                        compressed_data,
                        json.dumps(
                            {
                                "compressed": COMPRESSION_AVAILABLE,
                                "size": len(compressed_data),
                            },
                        ),
                    ),
                )

                # Update context state
                conn.execute(
                    """
                    UPDATE session_contexts
                    SET state = ?, preserved_at = ?, updated_at = ?
                    WHERE session_id = ?
                """,
                    (
                        ContextState.PRESERVED.value,
                        datetime.now(),
                        datetime.now(),
                        session_id,
                    ),
                )

            # Execute preservation callbacks
            for callback in self._preservation_callbacks:
                try:
                    await callback(context, snapshot_data)
                except Exception as e:
                    logger.exception(f"Preservation callback error: {e}")

            return True

        except Exception as e:
            logger.exception(f"Context preservation failed: {e}")
            return False

    async def restore_context(self, session_id: str) -> SessionContext | None:
        """Restore session context from snapshot."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Get latest snapshot
                snapshot_row = conn.execute(
                    """
                    SELECT * FROM context_snapshots
                    WHERE session_id = ? AND snapshot_type = 'preservation'
                    ORDER BY timestamp DESC LIMIT 1
                """,
                    (session_id,),
                ).fetchone()

                if not snapshot_row:
                    return None

                # Decompress and restore data
                compressed_data = snapshot_row["data"]
                metadata = json.loads(snapshot_row["metadata"] or "{}")

                if metadata.get("compressed", False) and COMPRESSION_AVAILABLE:
                    try:
                        decompressed = gzip.decompress(compressed_data)
                        snapshot_data = pickle.loads(decompressed)
                    except Exception as e:
                        logger.warning(f"Decompression failed: {e}")
                        snapshot_data = json.loads(compressed_data.decode())
                else:
                    snapshot_data = json.loads(compressed_data.decode())

                # Restore context
                context_dict = snapshot_data["context"]
                context = SessionContext(**context_dict)
                context.recovery_attempts += 1

                self.current_context = context

                # Update database
                conn.execute(
                    """
                    UPDATE session_contexts
                    SET state = ?, updated_at = ?, restore_count = restore_count + 1
                    WHERE session_id = ?
                """,
                    (ContextState.RESTORED.value, datetime.now(), session_id),
                )

            # Execute restoration callbacks
            for callback in self._restoration_callbacks:
                try:
                    await callback(context, snapshot_data)
                except Exception as e:
                    logger.exception(f"Restoration callback error: {e}")

            return context

        except Exception as e:
            logger.exception(f"Context restoration failed: {e}")
            return None

    async def get_interruption_history(
        self,
        user_id: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent interruption history."""
        since = datetime.now() - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT * FROM interruption_events
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """,
                (user_id, since),
            )

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result["source_context"] = json.loads(result["source_context"] or "{}")
                result["target_context"] = json.loads(result["target_context"] or "{}")
                result["recovery_data"] = json.loads(result["recovery_data"] or "{}")
                results.append(result)

            return results

    async def get_context_statistics(self, user_id: str) -> dict[str, Any]:
        """Get context preservation statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get session stats
            session_stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN state = 'preserved' THEN 1 END) as preserved_sessions,
                    COUNT(CASE WHEN state = 'restored' THEN 1 END) as restored_sessions,
                    AVG(restore_count) as avg_restore_count
                FROM session_contexts
                WHERE user_id = ?
            """,
                (user_id,),
            ).fetchone()

            # Get interruption stats
            interruption_stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total_interruptions,
                    COUNT(CASE WHEN auto_saved THEN 1 END) as auto_saved_interruptions,
                    AVG(duration) as avg_duration,
                    event_type,
                    COUNT(*) as type_count
                FROM interruption_events
                WHERE user_id = ?
                GROUP BY event_type
            """,
                (user_id,),
            ).fetchall()

            # Get snapshot stats
            snapshot_stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total_snapshots,
                    SUM(LENGTH(data)) as total_size,
                    AVG(LENGTH(data)) as avg_size
                FROM context_snapshots cs
                JOIN session_contexts sc ON cs.session_id = sc.session_id
                WHERE sc.user_id = ?
            """,
                (user_id,),
            ).fetchone()

            return {
                "sessions": dict(session_stats) if session_stats else {},
                "interruptions": {
                    "total": dict(interruption_stats[0])["total_interruptions"]
                    if interruption_stats
                    else 0,
                    "by_type": [dict(row) for row in interruption_stats]
                    if interruption_stats
                    else [],
                },
                "snapshots": dict(snapshot_stats) if snapshot_stats else {},
            }

    def register_preservation_callback(self, callback: Callable) -> None:
        """Register callback for context preservation."""
        self._preservation_callbacks.append(callback)

    def register_restoration_callback(self, callback: Callable) -> None:
        """Register callback for context restoration."""
        self._restoration_callbacks.append(callback)

    def _handle_interruption(self, event_data: dict[str, Any]) -> None:
        """Handle interruption event."""
        try:
            interruption_type = event_data["type"]
            timestamp = event_data["timestamp"]

            # Auto-save if enabled and threshold met
            if (
                self.auto_save_enabled
                and self.current_context
                and interruption_type
                in [InterruptionType.APP_SWITCH, InterruptionType.FOCUS_LOST]
            ):
                focus_duration = event_data.get("focus_duration", 0)
                if focus_duration >= self.save_threshold:
                    asyncio.create_task(self.preserve_context())

            # Log the interruption
            event_id = f"int_{int(time.time() * 1000)}"

            interruption = InterruptionEvent(
                id=event_id,
                event_type=interruption_type,
                timestamp=timestamp,
                source_context=event_data.get("source_context", {}),
                target_context=event_data.get("target_context", {}),
                duration=event_data.get("focus_duration"),
                recovery_data=None,
                auto_saved=self.auto_save_enabled,
                user_id=self.current_context.user_id
                if self.current_context
                else "unknown",
                project_id=self.current_context.project_id
                if self.current_context
                else None,
            )

            # Store in database
            asyncio.create_task(self._store_interruption(interruption))

            # Update current context
            if self.current_context:
                self.current_context.interruption_count += 1
                self.current_context.last_activity = timestamp

        except Exception as e:
            logger.exception(f"Interruption handling error: {e}")

    async def _store_interruption(self, interruption: InterruptionEvent) -> None:
        """Store interruption event in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO interruption_events
                    (id, event_type, timestamp, source_context, target_context, duration, recovery_data, auto_saved, user_id, project_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        interruption.id,
                        interruption.event_type.value,
                        interruption.timestamp,
                        json.dumps(interruption.source_context),
                        json.dumps(interruption.target_context),
                        interruption.duration,
                        json.dumps(interruption.recovery_data or {}),
                        interruption.auto_saved,
                        interruption.user_id,
                        interruption.project_id,
                    ),
                )
        except Exception as e:
            logger.exception(f"Failed to store interruption: {e}")

    def _capture_environment_state(self) -> dict[str, Any]:
        """Capture current environment state."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "cwd": Path.cwd().as_posix(),
            "processes": [],
        }

        # Capture running processes (limited for privacy)
        if PSUTIL_AVAILABLE:
            try:
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        name = proc.info["name"]
                        if any(
                            keyword in name.lower()
                            for keyword in ["code", "python", "node", "git"]
                        ):
                            state["processes"].append(
                                {"pid": proc.info["pid"], "name": name},
                            )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.debug(f"Process capture failed: {e}")

        return state


# Global manager instance
_interruption_manager = None


def get_interruption_manager() -> InterruptionManager:
    """Get global interruption manager instance."""
    global _interruption_manager
    if _interruption_manager is None:
        _interruption_manager = InterruptionManager()
    return _interruption_manager


# Public API functions for MCP tools
async def start_interruption_monitoring(
    working_directory: str = ".",
    watch_files: bool = True,
) -> None:
    """Start interruption monitoring."""
    manager = get_interruption_manager()
    manager.start_monitoring(working_directory, watch_files)


def stop_interruption_monitoring() -> None:
    """Stop interruption monitoring."""
    manager = get_interruption_manager()
    manager.stop_monitoring()


async def create_session_context(
    user_id: str,
    project_id: str | None = None,
    working_directory: str = ".",
) -> str:
    """Create new session context for interruption management."""
    manager = get_interruption_manager()
    return await manager.create_session_context(user_id, project_id, working_directory)


async def preserve_current_context(
    session_id: str | None = None,
    force: bool = False,
) -> bool:
    """Preserve current session context."""
    manager = get_interruption_manager()
    return await manager.preserve_context(session_id, force)


async def restore_session_context(session_id: str) -> dict[str, Any] | None:
    """Restore session context from snapshot."""
    manager = get_interruption_manager()
    context = await manager.restore_context(session_id)
    return asdict(context) if context else None


async def get_interruption_history(
    user_id: str,
    hours: int = 24,
) -> list[dict[str, Any]]:
    """Get recent interruption history for user."""
    manager = get_interruption_manager()
    return await manager.get_interruption_history(user_id, hours)


async def get_interruption_statistics(user_id: str) -> dict[str, Any]:
    """Get context preservation and interruption statistics."""
    manager = get_interruption_manager()
    return await manager.get_context_statistics(user_id)
