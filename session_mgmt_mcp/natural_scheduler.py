"""Natural Language Scheduling module for time-based reminders and triggers.

This module provides intelligent scheduling capabilities including:
- Natural language time parsing ("in 30 minutes", "tomorrow at 9am")
- Recurring reminders and cron-like scheduling
- Context-aware reminder triggers
- Integration with session workflow
"""

import asyncio
import importlib.util
import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

DATEUTIL_AVAILABLE = importlib.util.find_spec("dateutil") is not None
CRONTAB_AVAILABLE = importlib.util.find_spec("python_crontab") is not None
SCHEDULE_AVAILABLE = importlib.util.find_spec("schedule") is not None

if DATEUTIL_AVAILABLE:
    from dateutil import parser as date_parser
    from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class ReminderType(Enum):
    """Types of reminders."""

    ONE_TIME = "one_time"
    RECURRING = "recurring"
    CONTEXT_TRIGGER = "context_trigger"
    SESSION_MILESTONE = "session_milestone"


class ReminderStatus(Enum):
    """Reminder execution status."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class NaturalReminder:
    """Natural language reminder with scheduling information."""

    id: str
    title: str
    description: str
    reminder_type: ReminderType
    status: ReminderStatus
    created_at: datetime
    scheduled_for: datetime
    executed_at: datetime | None
    user_id: str
    project_id: str | None
    context_triggers: list[str]
    recurrence_rule: str | None
    notification_method: str
    metadata: dict[str, Any]


@dataclass
class SchedulingContext:
    """Context information for scheduling decisions."""

    current_time: datetime
    timezone: str
    user_preferences: dict[str, Any]
    active_project: str | None
    session_duration: int
    recent_activity: list[dict[str, Any]]


class NaturalLanguageParser:
    """Parses natural language time expressions."""

    def __init__(self) -> None:
        """Initialize natural language parser."""
        self.time_patterns = {
            # Relative time patterns
            r"in (\d+) (minute|min|minutes|mins)": lambda m: timedelta(
                minutes=int(m.group(1)),
            ),
            r"in (\d+) (hour|hours|hr|hrs)": lambda m: timedelta(hours=int(m.group(1))),
            r"in (\d+) (day|days)": lambda m: timedelta(days=int(m.group(1))),
            r"in (\d+) (week|weeks)": lambda m: timedelta(weeks=int(m.group(1))),
            r"in (\d+) (month|months)": lambda m: relativedelta(months=int(m.group(1)))
            if DATEUTIL_AVAILABLE
            else timedelta(days=int(m.group(1)) * 30),
            # Specific times
            r"tomorrow( at (\d{1,2}):?(\d{2})?)?(am|pm)?": self._parse_tomorrow,
            r"next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)": self._parse_next_weekday,
            r"at (\d{1,2}):?(\d{2})?\s*(am|pm)?": self._parse_specific_time,
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (\d{1,2}):?(\d{2})?\s*(am|pm)?": self._parse_weekday_time,
            # Session-relative
            r"end of (session|work)": lambda m: timedelta(
                hours=2,
            ),  # Default session length
            r"after (break|lunch)": lambda m: timedelta(hours=1),
            r"before (meeting|call)": lambda m: timedelta(minutes=15),
        }

        self.recurrence_patterns = {
            r"every (day|daily)": "FREQ=DAILY",
            r"every (week|weekly)": "FREQ=WEEKLY",
            r"every (month|monthly)": "FREQ=MONTHLY",
            r"every (\d+) (minute|minutes)": lambda m: f"FREQ=MINUTELY;INTERVAL={m.group(1)}",
            r"every (\d+) (hour|hours)": lambda m: f"FREQ=HOURLY;INTERVAL={m.group(1)}",
            r"every (\d+) (day|days)": lambda m: f"FREQ=DAILY;INTERVAL={m.group(1)}",
        }

    def parse_time_expression(
        self,
        expression: str,
        base_time: datetime | None = None,
    ) -> datetime | None:
        """Parse natural language time expression."""
        if not expression:
            return None

        base_time = base_time or datetime.now()
        expression = expression.lower().strip()

        # Try relative patterns first
        for pattern, handler in self.time_patterns.items():
            match = re.search(pattern, expression, re.IGNORECASE)
            if match:
                try:
                    if callable(handler):
                        if isinstance(handler(match), timedelta):
                            return base_time + handler(match)
                        if isinstance(handler(match), datetime):
                            return handler(match)
                        delta = handler(match)
                        if hasattr(delta, "days") or hasattr(delta, "months"):
                            return base_time + delta
                except Exception:
                    continue

        # Try dateutil parser for absolute dates
        if DATEUTIL_AVAILABLE:
            try:
                parsed_date = date_parser.parse(expression, default=base_time)
                if parsed_date > base_time:  # Only future dates
                    return parsed_date
            except (ValueError, TypeError):
                pass

        return None

    def parse_recurrence(self, expression: str) -> str | None:
        """Parse recurrence pattern from natural language."""
        if not expression:
            return None

        expression = expression.lower().strip()

        for pattern, handler in self.recurrence_patterns.items():
            match = re.search(pattern, expression, re.IGNORECASE)
            if match:
                if callable(handler):
                    return handler(match)
                return handler

        return None

    def _parse_tomorrow(self, match):
        """Parse 'tomorrow' with optional time."""
        tomorrow = datetime.now() + timedelta(days=1)

        if match.group(2) and match.group(3):  # Has time
            hour = int(match.group(2))
            minute = int(match.group(3))
            am_pm = match.group(4)

            if am_pm and am_pm.lower() == "pm" and hour != 12:
                hour += 12
            elif am_pm and am_pm.lower() == "am" and hour == 12:
                hour = 0

            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Default to 9 AM tomorrow
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    def _parse_next_weekday(self, match):
        """Parse 'next monday', etc."""
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        target_weekday = weekdays[match.group(1)]
        today = datetime.now()
        days_ahead = target_weekday - today.weekday()

        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7

        return today + timedelta(days=days_ahead)

    def _parse_specific_time(self, match):
        """Parse 'at 3:30pm' for today."""
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        am_pm = match.group(3)

        if am_pm and am_pm.lower() == "pm" and hour != 12:
            hour += 12
        elif am_pm and am_pm.lower() == "am" and hour == 12:
            hour = 0

        target_time = datetime.now().replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        # If time has passed today, schedule for tomorrow
        if target_time <= datetime.now():
            target_time += timedelta(days=1)

        return target_time

    def _parse_weekday_time(self, match):
        """Parse 'monday at 3pm'."""
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        target_weekday = weekdays[match.group(1)]
        hour = int(match.group(2))
        minute = int(match.group(3)) if match.group(3) else 0
        am_pm = match.group(4)

        if am_pm and am_pm.lower() == "pm" and hour != 12:
            hour += 12
        elif am_pm and am_pm.lower() == "am" and hour == 12:
            hour = 0

        today = datetime.now()
        days_ahead = target_weekday - today.weekday()

        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        elif days_ahead == 0:  # Today - check if time has passed
            target_time = today.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if target_time <= today:
                days_ahead = 7

        target_date = today + timedelta(days=days_ahead)
        return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


class ReminderScheduler:
    """Manages scheduling and execution of reminders."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize reminder scheduler."""
        self.db_path = db_path or str(
            Path.home() / ".claude" / "data" / "natural_scheduler.db",
        )
        self.parser = NaturalLanguageParser()
        self._lock = threading.Lock()
        self._running = False
        self._scheduler_thread = None
        self._callbacks: dict[str, list[Callable]] = {}
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for reminders."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    reminder_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP,
                    scheduled_for TIMESTAMP,
                    executed_at TIMESTAMP,
                    user_id TEXT NOT NULL,
                    project_id TEXT,
                    context_triggers TEXT,  -- JSON array
                    recurrence_rule TEXT,
                    notification_method TEXT,
                    metadata TEXT  -- JSON object
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminder_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    result TEXT,
                    details TEXT  -- JSON object
                )
            """)

            # Create indices
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_scheduled ON reminders(scheduled_for)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_project ON reminders(project_id)",
            )

    async def create_reminder(
        self,
        title: str,
        time_expression: str,
        description: str = "",
        user_id: str = "default",
        project_id: str | None = None,
        notification_method: str = "session",
        context_triggers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Create a new reminder from natural language."""
        # Parse the time expression
        scheduled_time = self.parser.parse_time_expression(time_expression)
        if not scheduled_time:
            return None

        # Check for recurrence
        recurrence_rule = self.parser.parse_recurrence(time_expression)
        reminder_type = (
            ReminderType.RECURRING if recurrence_rule else ReminderType.ONE_TIME
        )

        # Generate reminder ID
        reminder_id = f"rem_{int(time.time() * 1000)}"

        reminder = NaturalReminder(
            id=reminder_id,
            title=title,
            description=description,
            reminder_type=reminder_type,
            status=ReminderStatus.PENDING,
            created_at=datetime.now(),
            scheduled_for=scheduled_time,
            executed_at=None,
            user_id=user_id,
            project_id=project_id,
            context_triggers=context_triggers or [],
            recurrence_rule=recurrence_rule,
            notification_method=notification_method,
            metadata=metadata or {},
        )

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reminders (id, title, description, reminder_type, status, created_at,
                                     scheduled_for, executed_at, user_id, project_id, context_triggers,
                                     recurrence_rule, notification_method, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    reminder.id,
                    reminder.title,
                    reminder.description,
                    reminder.reminder_type.value,
                    reminder.status.value,
                    reminder.created_at,
                    reminder.scheduled_for,
                    reminder.executed_at,
                    reminder.user_id,
                    reminder.project_id,
                    json.dumps(reminder.context_triggers),
                    reminder.recurrence_rule,
                    reminder.notification_method,
                    json.dumps(reminder.metadata),
                ),
            )

        # Log creation
        await self._log_reminder_action(
            reminder_id,
            "created",
            "success",
            {
                "scheduled_for": scheduled_time.isoformat(),
                "time_expression": time_expression,
            },
        )

        return reminder_id

    async def get_pending_reminders(
        self,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get pending reminders."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            where_conditions = ["status IN ('pending', 'active')"]
            params = []

            if user_id:
                where_conditions.append("user_id = ?")
                params.append(user_id)

            if project_id:
                where_conditions.append("project_id = ?")
                params.append(project_id)

            query = f"SELECT * FROM reminders WHERE {' AND '.join(where_conditions)} ORDER BY scheduled_for"

            cursor = conn.execute(query, params)
            results = []

            for row in cursor.fetchall():
                result = dict(row)
                result["context_triggers"] = json.loads(
                    result["context_triggers"] or "[]",
                )
                result["metadata"] = json.loads(result["metadata"] or "{}")
                results.append(result)

            return results

    async def get_due_reminders(
        self,
        check_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get reminders that are due for execution."""
        check_time = check_time or datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status = 'pending' AND scheduled_for <= ?
                ORDER BY scheduled_for
            """,
                (check_time,),
            )

            results = []
            for row in cursor.fetchall():
                result = dict(row)
                result["context_triggers"] = json.loads(
                    result["context_triggers"] or "[]",
                )
                result["metadata"] = json.loads(result["metadata"] or "{}")
                results.append(result)

            return results

    async def execute_reminder(self, reminder_id: str) -> bool:
        """Execute a due reminder."""
        try:
            # Get reminder details
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM reminders WHERE id = ?",
                    (reminder_id,),
                ).fetchone()

                if not row:
                    return False

                reminder_data = dict(row)
                reminder_data["context_triggers"] = json.loads(
                    reminder_data["context_triggers"] or "[]",
                )
                reminder_data["metadata"] = json.loads(
                    reminder_data["metadata"] or "{}",
                )

            # Execute callbacks
            callbacks = self._callbacks.get(reminder_data["notification_method"], [])
            for callback in callbacks:
                try:
                    await callback(reminder_data)
                except Exception as e:
                    logger.exception(f"Callback error for reminder {reminder_id}: {e}")

            # Update status
            now = datetime.now()
            new_status = ReminderStatus.COMPLETED

            # Handle recurring reminders
            if reminder_data["recurrence_rule"]:
                # Schedule next occurrence
                next_time = self._calculate_next_occurrence(
                    reminder_data["scheduled_for"],
                    reminder_data["recurrence_rule"],
                )
                if next_time:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute(
                            """
                            UPDATE reminders
                            SET scheduled_for = ?, status = 'pending', executed_at = NULL
                            WHERE id = ?
                        """,
                            (next_time, reminder_id),
                        )

                    await self._log_reminder_action(
                        reminder_id,
                        "rescheduled",
                        "success",
                        {"next_occurrence": next_time.isoformat()},
                    )
                    return True

            # Mark as completed
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = ?, executed_at = ?
                    WHERE id = ?
                """,
                    (new_status.value, now, reminder_id),
                )

            await self._log_reminder_action(
                reminder_id,
                "executed",
                "success",
                {"executed_at": now.isoformat()},
            )

            return True

        except Exception as e:
            await self._log_reminder_action(
                reminder_id,
                "executed",
                "failed",
                {"error": str(e)},
            )
            return False

    async def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a pending reminder."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    """
                    UPDATE reminders
                    SET status = ?
                    WHERE id = ? AND status IN ('pending', 'active')
                """,
                    (ReminderStatus.CANCELLED.value, reminder_id),
                )

                success = result.rowcount > 0

            if success:
                await self._log_reminder_action(reminder_id, "cancelled", "success", {})

            return success

        except Exception as e:
            await self._log_reminder_action(
                reminder_id,
                "cancelled",
                "failed",
                {"error": str(e)},
            )
            return False

    def register_notification_callback(self, method: str, callback: Callable) -> None:
        """Register callback for notification method."""
        if method not in self._callbacks:
            self._callbacks[method] = []
        self._callbacks[method].append(callback)

    def start_scheduler(self) -> None:
        """Start the background scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
        )
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5.0)

    def _scheduler_loop(self) -> None:
        """Background scheduler loop."""
        while self._running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._check_and_execute_reminders())
            except Exception as e:
                logger.exception(f"Scheduler loop error: {e}")
            finally:
                if loop and not loop.is_closed():
                    loop.close()
                time.sleep(60)  # Check every minute

    async def _check_and_execute_reminders(self) -> None:
        """Check for due reminders and execute them."""
        due_reminders = await self.get_due_reminders()

        for reminder in due_reminders:
            await self.execute_reminder(reminder["id"])

    def _calculate_next_occurrence(
        self,
        last_time: datetime,
        recurrence_rule: str,
    ) -> datetime | None:
        """Calculate next occurrence for recurring reminder."""
        if not DATEUTIL_AVAILABLE:
            return None

        try:
            # Simple rule parsing (extend as needed)
            if recurrence_rule.startswith("FREQ=DAILY"):
                return last_time + timedelta(days=1)
            if recurrence_rule.startswith("FREQ=WEEKLY"):
                return last_time + timedelta(weeks=1)
            if recurrence_rule.startswith("FREQ=MONTHLY"):
                return last_time + relativedelta(months=1)
            if "INTERVAL=" in recurrence_rule:
                # Parse interval from rule like "FREQ=HOURLY;INTERVAL=2"
                parts = recurrence_rule.split(";")
                interval = 1
                freq = None

                for part in parts:
                    if part.startswith("FREQ="):
                        freq = part.split("=")[1]
                    elif part.startswith("INTERVAL="):
                        interval = int(part.split("=")[1])

                if freq == "HOURLY":
                    return last_time + timedelta(hours=interval)
                if freq == "MINUTELY":
                    return last_time + timedelta(minutes=interval)
                if freq == "DAILY":
                    return last_time + timedelta(days=interval)

        except Exception as e:
            logger.exception(f"Error calculating next occurrence: {e}")

        return None

    async def _log_reminder_action(
        self,
        reminder_id: str,
        action: str,
        result: str,
        details: dict[str, Any],
    ) -> None:
        """Log reminder action for audit trail."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reminder_history (reminder_id, action, timestamp, result, details)
                VALUES (?, ?, ?, ?, ?)
            """,
                (reminder_id, action, datetime.now(), result, json.dumps(details)),
            )


# Global scheduler instance
_reminder_scheduler = None


def get_reminder_scheduler() -> ReminderScheduler:
    """Get global reminder scheduler instance."""
    global _reminder_scheduler
    if _reminder_scheduler is None:
        _reminder_scheduler = ReminderScheduler()
    return _reminder_scheduler


# Public API functions for MCP tools
async def create_natural_reminder(
    title: str,
    time_expression: str,
    description: str = "",
    user_id: str = "default",
    project_id: str | None = None,
    notification_method: str = "session",
) -> str | None:
    """Create reminder from natural language time expression."""
    scheduler = get_reminder_scheduler()
    return await scheduler.create_reminder(
        title,
        time_expression,
        description,
        user_id,
        project_id,
        notification_method,
    )


async def list_user_reminders(
    user_id: str = "default",
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List pending reminders for user/project."""
    scheduler = get_reminder_scheduler()
    return await scheduler.get_pending_reminders(user_id, project_id)


async def cancel_user_reminder(reminder_id: str) -> bool:
    """Cancel a specific reminder."""
    scheduler = get_reminder_scheduler()
    return await scheduler.cancel_reminder(reminder_id)


async def check_due_reminders() -> list[dict[str, Any]]:
    """Check for reminders that are due now."""
    scheduler = get_reminder_scheduler()
    return await scheduler.get_due_reminders()


def start_reminder_service() -> None:
    """Start the background reminder service."""
    scheduler = get_reminder_scheduler()
    scheduler.start_scheduler()


def stop_reminder_service() -> None:
    """Stop the background reminder service."""
    scheduler = get_reminder_scheduler()
    scheduler.stop_scheduler()


def register_session_notifications() -> None:
    """Register session-based notification callbacks."""
    scheduler = get_reminder_scheduler()

    async def session_notification(reminder_data: dict[str, Any]) -> None:
        """Default session notification handler."""
        logger.info(
            f"Reminder: {reminder_data['title']} - {reminder_data['description']}",
        )

    scheduler.register_notification_callback("session", session_notification)
