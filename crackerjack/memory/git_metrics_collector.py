"""Git metrics collector for development velocity and pattern analysis.

This module provides:
- Git log parsing and commit metrics calculation
- Branch activity tracking (creation, deletion, switches)
- Merge and rebase pattern detection
- Conventional commit compliance tracking
- Time-series metrics storage in SQLite

Security:
- Uses SecureSubprocessExecutor for all git commands
- Validates repository paths to prevent traversal
- No shell=True subprocess execution
"""

from __future__ import annotations

import logging
import re
import sqlite3
import subprocess
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from crackerjack.services.secure_subprocess import (
    SecureSubprocessExecutor,
    SubprocessSecurityConfig,
)

logger = logging.getLogger(__name__)

def _create_git_executor() -> SecureSubprocessExecutor:
    """Create a subprocess executor configured for git commands.

    Adds git-specific safe patterns to allow format strings and refs.
    """
    config = SubprocessSecurityConfig(
        allowed_executables={"git"},
        enable_command_logging=False,
    )
    executor = SecureSubprocessExecutor(config)

    # Add git-specific safe patterns for format strings and refs
    git_patterns = [
        r'^--pretty=format:.*$',  # Git log format strings
        r'^--format=.*$',          # Git format shorthand
        r'^--date=.*$',            # Git date format
        r'^--since=.*$',
        r'^--until=.*$',
        r'^-.*',                   # Git short options (may contain special chars)
        r'^.*@{.*}.*$',           # Git reflog refs
    ]

    executor.allowed_git_patterns.extend(git_patterns)
    return executor




# Conventional commit types per conventionalcommits.org
CONVENTIONAL_TYPES = {
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "test",
    "chore",
    "perf",
    "ci",
    "build",
    "revert",
}


@dataclass(frozen=True)
class CommitData:
    """Raw commit information from git log."""

    hash: str
    author_timestamp: datetime
    author_name: str
    author_email: str
    message: str
    is_merge: bool = False
    is_conventional: bool = False
    conventional_type: str | None = None
    conventional_scope: str | None = None
    has_breaking_change: bool = False


@dataclass(frozen=True)
class BranchEvent:
    """Branch creation or deletion event."""

    branch_name: str
    event_type: t.Literal["created", "deleted", "checkout"]
    timestamp: datetime
    commit_hash: str | None = None


@dataclass(frozen=True)
class MergeEvent:
    """Merge or rebase event."""

    merge_hash: str
    merge_timestamp: datetime
    merge_type: t.Literal["merge", "rebase", "cherry-pick"]
    source_branch: str | None
    target_branch: str | None
    has_conflicts: bool
    conflict_files: list[str] = field(default_factory=list)


@dataclass
class CommitMetrics:
    """Commit velocity metrics over time periods."""

    total_commits: int
    conventional_commits: int
    conventional_compliance_rate: float
    breaking_changes: int
    avg_commits_per_hour: float
    avg_commits_per_day: float
    avg_commits_per_week: float
    most_active_hour: int  # 0-23
    most_active_day: int  # 0=Monday, 6=Sunday
    time_period: timedelta


@dataclass
class BranchMetrics:
    """Branch activity metrics."""

    total_branches: int
    active_branches: int  # Branches with commits in time period
    branch_switches: int
    branches_created: int
    branches_deleted: int
    avg_branch_lifetime_hours: float
    most_switched_branch: str | None


@dataclass
class MergeMetrics:
    """Merge and conflict metrics."""

    total_merges: int
    total_rebases: int
    total_conflicts: int
    conflict_rate: float  # Conflicts per merge operation
    avg_files_per_conflict: float
    most_conflicted_files: list[tuple[str, int]]  # (filename, conflict_count)
    merge_success_rate: float


@dataclass
class VelocityDashboard:
    """Aggregated velocity dashboard for specified time period."""

    period_start: datetime
    period_end: datetime
    commit_metrics: CommitMetrics
    branch_metrics: BranchMetrics
    merge_metrics: MergeMetrics
    trend_data: list[tuple[datetime, int]]  # (date, commit_count)


class _ConventionalCommitParser:
    """Parser for conventional commits specification."""

    # Pattern: type(scope)!: subject
    # Examples:
    #   feat: add new feature
    #   fix(auth): resolve login issue
    #   feat(api)!: breaking API change
    PATTERN = re.compile(
        r"""^
        (?P<type>[a-z]+)                    # Conventional type
        (?:\((?P<scope>[^)]+)\))?          # Optional scope
        (?P<breaking>!)?                    # Breaking change indicator
        :\s*                                # Separator
        (?P<subject>.+?)                    # Subject
        (?:\n\n.+)?                         # Optional body/footer
        $""",
        re.VERBOSE | re.MULTILINE,
    )

    # BREAKING CHANGE: in footer
    BREAKING_PATTERN = re.compile(
        r"""^BREAKING\sCHANGE:\s+(.+)$""",
        re.MULTILINE,
    )

    @classmethod
    def parse(cls, commit_message: str) -> tuple[bool, str | None, str | None, bool]:
        """Parse commit message for conventional compliance.

        Args:
            commit_message: Full commit message

        Returns:
            (is_conventional, type, scope, has_breaking_change)
        """
        match = cls.PATTERN.search(commit_message)
        if not match:
            # Check for BREAKING CHANGE footer
            if cls.BREAKING_PATTERN.search(commit_message):
                return False, None, None, True
            return False, None, None, False

        commit_type = match.group("type")
        scope = match.group("scope")
        breaking_indicator = match.group("breaking") is not None

        # Check for BREAKING CHANGE footer
        has_breaking = breaking_indicator or cls.BREAKING_PATTERN.search(
            commit_message
        ) is not None

        # Verify type is conventional
        is_conventional = commit_type in CONVENTIONAL_TYPES

        return is_conventional, commit_type, scope, has_breaking


class _GitRepository:
    """Git repository interface using secure subprocess execution."""

    def __init__(self, repo_path: Path, executor: SecureSubprocessExecutor) -> None:
        """Initialize git repository interface.

        Args:
            repo_path: Path to git repository
            executor: Secure subprocess executor for git commands

        Raises:
            ValueError: If repo_path is not a valid git repository
        """
        self.repo_path = repo_path.resolve()
        self.executor = executor

        # Validate this is a git repository
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _git_command(
        self,
        args: list[str],
        timeout: float = 30.0,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Execute git command securely.

        Args:
            args: Git arguments (e.g., ["log", "--oneline"])
            timeout: Command timeout in seconds
            check: Raise exception on non-zero exit

        Returns:
            Completed process with stdout/stderr
        """
        cmd = ["git", "-C", str(self.repo_path)] + args

        try:
            return self.executor.execute_secure(
                command=cmd,
                cwd=self.repo_path,
                timeout=timeout,
                check=check,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {' '.join(cmd)}")
            logger.error(f"stderr: {e.stderr}")
            raise

    def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[CommitData]:
        """Parse git log into structured commit data.

        Args:
            since: Start datetime (inclusive)
            until: End datetime (inclusive)

        Returns:
            List of commit data
        """
        # Build git log command
        # Format: hash|iso_timestamp|author_name|author_email|subject
        cmd = [
            "log",
            '--pretty=format:%H|%ai|%an|%ae|%s',
        ]

        if since:
            cmd.append(f"--since={since.isoformat()}")
        if until:
            cmd.append(f"--until={until.isoformat()}")

        result = self._git_command(cmd, timeout=60.0)

        commits: list[CommitData] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                parts = line.split("|", 4)
                if len(parts) != 5:
                    continue

                hash_val, timestamp_str, author, email, message = parts

                # Parse ISO timestamp
                timestamp = datetime.fromisoformat(timestamp_str)

                # Check if merge commit
                is_merge = message.startswith("Merge ")

                # Parse conventional commit
                (
                    is_conventional,
                    conv_type,
                    conv_scope,
                    has_breaking,
                ) = _ConventionalCommitParser.parse(message)

                commits.append(
                    CommitData(
                        hash=hash_val,
                        author_timestamp=timestamp,
                        author_name=author,
                        author_email=email,
                        message=message,
                        is_merge=is_merge,
                        is_conventional=is_conventional,
                        conventional_type=conv_type,
                        conventional_scope=conv_scope,
                        has_breaking_change=has_breaking,
                    )
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse commit line: {line[:100]}... - {e}")
                continue

        return commits

    def get_branches(self) -> dict[str, str]:
        """Get all branches with their HEAD commits.

        Returns:
            Dict mapping branch name to commit hash
        """
        cmd = ["branch", "-vv", "--format=%(refname:short)%09%(objectname)"]
        result = self._git_command(cmd)

        branches: dict[str, str] = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) == 2:
                branch, commit = parts
                branches[branch] = commit

        return branches

    def get_reflog_events(self, since: datetime | None = None) -> list[BranchEvent]:
        """Parse git reflog for branch activity events.

        Args:
            since: Start datetime for events

        Returns:
            List of branch events (checkout, creation, deletion)
        """
        cmd = ["reflog", "show", "--date=iso", "--pretty=%H|%gd|%gs"]

        if since:
            cmd.append(f"--since={since.isoformat()}")

        result = self._git_command(cmd, timeout=60.0, check=False)

        events: list[BranchEvent] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                parts = line.split("|")
                if len(parts) < 2:
                    continue

                commit_hash, ref, selector = parts[0], parts[1], parts[2] if len(parts) > 2 else ""

                # Extract timestamp from reflog output
                # Format: HEAD@{2025-01-15 10:30:00 -0800}
                timestamp_match = re.search(r"\{(.+?)\}", ref)
                if not timestamp_match:
                    continue

                timestamp_str = timestamp_match.group(1)
                timestamp = datetime.strptime(
                    timestamp_str.split("+")[0].strip(),
                    "%Y-%m-%d %H:%M:%S",
                )

                # Detect event type
                if "checkout" in selector.lower():
                    branch_name = selector.split(":")[-1] if ":" in selector else None
                    if branch_name:
                        events.append(
                            BranchEvent(
                                branch_name=branch_name,
                                event_type="checkout",
                                timestamp=timestamp,
                                commit_hash=commit_hash,
                            )
                        )

            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse reflog line: {line[:100]}... - {e}")
                continue

        return events

    def get_merge_history(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[MergeEvent]:
        """Get merge and rebase history with conflict detection.

        Args:
            since: Start datetime
            until: End datetime

        Returns:
            List of merge events
        """
        # Get merge commits
        cmd = ["log", "--merges", "--pretty=format:%H|%ai|%s"]

        if since:
            cmd.append(f"--since={since.isoformat()}")
        if until:
            cmd.append(f"--until={until.isoformat()}")

        result = self._git_command(cmd, timeout=60.0, check=False)

        merge_events: list[MergeEvent] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                parts = line.split("|", 2)
                if len(parts) != 3:
                    continue

                merge_hash, timestamp_str, message = parts
                timestamp = datetime.fromisoformat(timestamp_str)

                # Parse merge message
                # Examples:
                #   "Merge branch 'feature-xyz'"
                #   "Merge pull request #123 from user/branch"
                source_branch: str | None = None
                target_branch: str | None = None

                merge_match = re.search(r"Merge branch ['\"](.+?)['\"]", message)
                if merge_match:
                    source_branch = merge_match.group(1)

                pr_match = re.search(r"Merge pull request #\d+ from (.+?)", message)
                if pr_match:
                    source_branch = pr_match.group(1).split("/")[-1]

                # Detect conflicts by checking merge commit content
                # Conflicted files have conflict markers in the diff
                has_conflicts = self._check_merge_conflicts(merge_hash)
                conflict_files = (
                    self._get_conflict_files(merge_hash) if has_conflicts else []
                )

                merge_events.append(
                    MergeEvent(
                        merge_hash=merge_hash,
                        merge_timestamp=timestamp,
                        merge_type="merge",
                        source_branch=source_branch,
                        target_branch=target_branch,
                        has_conflicts=has_conflicts,
                        conflict_files=conflict_files,
                    )
                )

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse merge line: {line[:100]}... - {e}")
                continue

        return merge_events

    def _check_merge_conflicts(self, merge_hash: str) -> bool:
        """Check if merge had conflicts.

        Args:
            merge_hash: Merge commit hash

        Returns:
            True if merge had conflicts
        """
        # Check for conflict markers in merge commit parents
        cmd = ["show", "--pretty=%P", "--no-patch", merge_hash]
        result = self._git_command(cmd, timeout=10.0)

        # Merge commits have 2+ parents
        parents = result.stdout.strip().split()
        return len(parents) >= 2

    def _get_conflict_files(self, merge_hash: str) -> list[str]:
        """Get list of files that had conflicts in merge.

        Args:
            merge_hash: Merge commit hash

        Returns:
            List of file paths with conflicts
        """
        # This is a simplified check - full implementation would parse
        # the merge commit diff for conflict markers
        cmd = ["diff", "--name-only", f"{merge_hash}^1", f"{merge_hash}^2"]
        result = self._git_command(cmd, timeout=10.0, check=False)

        return result.stdout.strip().split("\n") if result.stdout.strip() else []


class GitMetricsStorage:
    """Time-series storage for git metrics."""

    def __init__(self, db_path: Path) -> None:
        """Initialize metrics storage.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database schema if not exists."""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            # Create tables
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    commit_hash TEXT UNIQUE NOT NULL,
                    author_timestamp TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_merge BOOLEAN DEFAULT 0,
                    is_conventional BOOLEAN DEFAULT 0,
                    conventional_type TEXT,
                    conventional_scope TEXT,
                    has_breaking_change BOOLEAN DEFAULT 0,
                    recorded_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_branch_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    commit_hash TEXT,
                    recorded_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_merge_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merge_hash TEXT UNIQUE NOT NULL,
                    merge_timestamp TEXT NOT NULL,
                    merge_type TEXT NOT NULL,
                    source_branch TEXT,
                    target_branch TEXT,
                    has_conflicts BOOLEAN DEFAULT 0,
                    conflict_files TEXT,  -- JSON array
                    recorded_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_metrics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    total_commits INTEGER DEFAULT 0,
                    conventional_commits INTEGER DEFAULT 0,
                    conventional_compliance_rate REAL DEFAULT 0.0,
                    breaking_changes INTEGER DEFAULT 0,
                    avg_commits_per_day REAL DEFAULT 0.0,
                    avg_commits_per_hour REAL DEFAULT 0.0,
                    avg_commits_per_week REAL DEFAULT 0.0,
                    total_branches INTEGER DEFAULT 0,
                    active_branches INTEGER DEFAULT 0,
                    branch_switches INTEGER DEFAULT 0,
                    total_merges INTEGER DEFAULT 0,
                    total_conflicts INTEGER DEFAULT 0,
                    conflict_rate REAL DEFAULT 0.0,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(snapshot_date, period_start, period_end)
                )
            """)

            # Create indexes
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_commits_timestamp
                ON git_commits(author_timestamp)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_branch_events_timestamp
                ON git_branch_events(timestamp)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_merge_events_timestamp
                ON git_merge_events(merge_timestamp)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_date
                ON git_metrics_snapshots(snapshot_date)
            """)

            self.conn.commit()
            logger.info(f"Git metrics storage initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize git metrics database: {e}")
            raise

    def store_commits(self, commits: list[CommitData]) -> int:
        """Store commit records.

        Args:
            commits: List of commit data

        Returns:
            Number of new commits stored
        """
        if not self.conn:
            return 0

        new_count = 0
        recorded_at = datetime.now().isoformat()

        cursor = self.conn.cursor()
        for commit in commits:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO git_commits
                    (commit_hash, author_timestamp, author_name, author_email, message,
                     is_merge, is_conventional, conventional_type, conventional_scope,
                     has_breaking_change, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        commit.hash,
                        commit.author_timestamp.isoformat(),
                        commit.author_name,
                        commit.author_email,
                        commit.message,
                        commit.is_merge,
                        commit.is_conventional,
                        commit.conventional_type,
                        commit.conventional_scope,
                        commit.has_breaking_change,
                        recorded_at,
                    ),
                )
                if cursor.rowcount > 0:
                    new_count += 1
            except sqlite3.Error as e:
                logger.debug(f"Failed to store commit {commit.hash}: {e}")

        self.conn.commit()
        return new_count

    def store_branch_events(self, events: list[BranchEvent]) -> int:
        """Store branch event records.

        Args:
            events: List of branch events

        Returns:
            Number of events stored
        """
        if not self.conn:
            return 0

        stored_count = 0
        recorded_at = datetime.now().isoformat()

        for event in events:
            try:
                self.conn.execute(
                    """
                    INSERT INTO git_branch_events
                    (branch_name, event_type, timestamp, commit_hash, recorded_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.branch_name,
                        event.event_type,
                        event.timestamp.isoformat(),
                        event.commit_hash,
                        recorded_at,
                    ),
                )
                stored_count += 1
            except sqlite3.Error as e:
                logger.debug(f"Failed to store branch event: {e}")

        self.conn.commit()
        return stored_count

    def store_merge_events(self, events: list[MergeEvent]) -> int:
        """Store merge event records.

        Args:
            events: List of merge events

        Returns:
            Number of events stored
        """
        if not self.conn:
            return 0

        stored_count = 0
        recorded_at = datetime.now().isoformat()

        import json

        cursor = self.conn.cursor()
        for event in events:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO git_merge_events
                    (merge_hash, merge_timestamp, merge_type, source_branch, target_branch,
                     has_conflicts, conflict_files, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.merge_hash,
                        event.merge_timestamp.isoformat(),
                        event.merge_type,
                        event.source_branch,
                        event.target_branch,
                        event.has_conflicts,
                        json.dumps(event.conflict_files),
                        recorded_at,
                    ),
                )
                if cursor.rowcount > 0:
                    stored_count += 1
            except sqlite3.Error as e:
                logger.debug(f"Failed to store merge event {event.merge_hash}: {e}")

        self.conn.commit()
        return stored_count

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


class GitMetricsCollector:
    """Collect and analyze git repository metrics.

    Provides:
    - Commit velocity tracking (commits per hour/day/week)
    - Branch activity analysis (switches, creation, deletion)
    - Merge pattern detection (conflicts, rebase frequency)
    - Conventional commit compliance
    - Time-series metrics storage
    """

    def __init__(
        self,
        repo_path: Path,
        storage_path: Path | None = None,
    ) -> None:
        """Initialize git metrics collector.

        Args:
            repo_path: Path to git repository
            storage_path: Path to metrics database (defaults to .git/metrics.db)
        """
        self.repo_path = repo_path.resolve()

        # Configure secure subprocess executor with git-specific patterns
        self.executor = _create_git_executor()

        # Initialize git repository interface
        self.git = _GitRepository(self.repo_path, self.executor)

        # Initialize storage
        if storage_path is None:
            storage_path = self.repo_path / ".git" / "git_metrics.db"
        self.storage = GitMetricsStorage(storage_path)

        logger.info(f"GitMetricsCollector initialized for {self.repo_path}")

    def collect_commit_metrics(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> CommitMetrics:
        """Calculate commit velocity metrics.

        Args:
            since: Start datetime (defaults to 30 days ago)
            until: End datetime (defaults to now)

        Returns:
            Commit metrics
        """
        if since is None:
            since = datetime.now() - timedelta(days=30)
        if until is None:
            until = datetime.now()

        commits = self.git.get_commits(since=since, until=until)

        if not commits:
            time_period = until - since
            return CommitMetrics(
                total_commits=0,
                conventional_commits=0,
                conventional_compliance_rate=0.0,
                breaking_changes=0,
                avg_commits_per_hour=0.0,
                avg_commits_per_day=0.0,
                avg_commits_per_week=0.0,
                most_active_hour=0,
                most_active_day=0,
                time_period=time_period,
            )

        # Calculate metrics
        total_commits = len(commits)
        conventional_commits = sum(1 for c in commits if c.is_conventional)
        breaking_changes = sum(1 for c in commits if c.has_breaking_change)

        compliance_rate = conventional_commits / total_commits if total_commits > 0 else 0.0

        # Time period
        time_period = until - since
        hours = max(time_period.total_seconds() / 3600, 1.0)
        days = max(time_period.total_seconds() / 86400, 1.0)
        weeks = max(days / 7, 1.0)

        avg_commits_per_hour = total_commits / hours
        avg_commits_per_day = total_commits / days
        avg_commits_per_week = total_commits / weeks

        # Find most active hour and day
        hour_counts: dict[int, int] = {}
        day_counts: dict[int, int] = {}

        for commit in commits:
            hour = commit.author_timestamp.hour
            day = commit.author_timestamp.weekday()

            hour_counts[hour] = hour_counts.get(hour, 0) + 1
            day_counts[day] = day_counts.get(day, 0) + 1

        most_active_hour = max(hour_counts, key=hour_counts.get) if hour_counts else 0
        most_active_day = max(day_counts, key=day_counts.get) if day_counts else 0

        # Store commits
        self.storage.store_commits(commits)

        return CommitMetrics(
            total_commits=total_commits,
            conventional_commits=conventional_commits,
            conventional_compliance_rate=compliance_rate,
            breaking_changes=breaking_changes,
            avg_commits_per_hour=avg_commits_per_hour,
            avg_commits_per_day=avg_commits_per_day,
            avg_commits_per_week=avg_commits_per_week,
            most_active_hour=most_active_hour,
            most_active_day=most_active_day,
            time_period=time_period,
        )

    def collect_branch_activity(
        self,
        since: datetime | None = None,
    ) -> BranchMetrics:
        """Calculate branch activity metrics.

        Args:
            since: Start datetime (defaults to 7 days ago)

        Returns:
            Branch metrics
        """
        if since is None:
            since = datetime.now() - timedelta(days=7)

        # Get current branches
        branches = self.git.get_branches()
        total_branches = len(branches)

        # Get reflog events
        events = self.git.get_reflog_events(since=since)

        # Store events
        self.storage.store_branch_events(events)

        # Calculate metrics
        branch_switches = sum(1 for e in events if e.event_type == "checkout")
        branches_created = sum(1 for e in events if e.event_type == "created")
        branches_deleted = sum(1 for e in events if e.event_type == "deleted")

        # Find most active branches
        branch_switch_counts: dict[str, int] = {}
        for event in events:
            if event.event_type == "checkout":
                branch_switch_counts[event.branch_name] = (
                    branch_switch_counts.get(event.branch_name, 0) + 1
                )

        most_switched = (
            max(branch_switch_counts, key=branch_switch_counts.get)
            if branch_switch_counts
            else None
        )

        # Active branches (with activity in period)
        active_branches = len(branch_switch_counts)

        # Average branch lifetime (simplified - would need branch creation history)
        avg_lifetime_hours = 0.0  # Placeholder

        return BranchMetrics(
            total_branches=total_branches,
            active_branches=active_branches,
            branch_switches=branch_switches,
            branches_created=branches_created,
            branches_deleted=branches_deleted,
            avg_branch_lifetime_hours=avg_lifetime_hours,
            most_switched_branch=most_switched,
        )

    def collect_merge_patterns(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> MergeMetrics:
        """Calculate merge and conflict metrics.

        Args:
            since: Start datetime
            until: End datetime

        Returns:
            Merge metrics
        """
        if since is None:
            since = datetime.now() - timedelta(days=30)
        if until is None:
            until = datetime.now()

        merge_events = self.git.get_merge_history(since=since, until=until)

        # Store merge events
        self.storage.store_merge_events(merge_events)

        if not merge_events:
            return MergeMetrics(
                total_merges=0,
                total_rebases=0,
                total_conflicts=0,
                conflict_rate=0.0,
                avg_files_per_conflict=0.0,
                most_conflicted_files=[],
                merge_success_rate=1.0,
            )

        total_merges = len(merge_events)
        total_rebases = sum(1 for e in merge_events if e.merge_type == "rebase")
        total_conflicts = sum(1 for e in merge_events if e.has_conflicts)

        conflict_rate = total_conflicts / total_merges if total_merges > 0 else 0.0

        # Calculate avg files per conflict
        conflict_events = [e for e in merge_events if e.has_conflicts]
        if conflict_events:
            total_files = sum(len(e.conflict_files) for e in conflict_events)
            avg_files = total_files / len(conflict_events)
        else:
            avg_files = 0.0

        # Find most conflicted files
        file_conflict_counts: dict[str, int] = {}
        for event in merge_events:
            for file_path in event.conflict_files:
                file_conflict_counts[file_path] = file_conflict_counts.get(file_path, 0) + 1

        most_conflicted = sorted(
            file_conflict_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        merge_success_rate = 1.0 - conflict_rate

        return MergeMetrics(
            total_merges=total_merges,
            total_rebases=total_rebases,
            total_conflicts=total_conflicts,
            conflict_rate=conflict_rate,
            avg_files_per_conflict=avg_files,
            most_conflicted_files=most_conflicted,
            merge_success_rate=merge_success_rate,
        )

    def get_velocity_dashboard(
        self,
        days_back: int = 30,
    ) -> VelocityDashboard:
        """Get aggregated velocity dashboard.

        Args:
            days_back: Number of days to analyze

        Returns:
            Velocity dashboard with all metrics
        """
        until = datetime.now()
        since = until - timedelta(days=days_back)

        # Collect all metrics
        commit_metrics = self.collect_commit_metrics(since=since, until=until)
        branch_metrics = self.collect_branch_activity(since=since)
        merge_metrics = self.collect_merge_patterns(since=since, until=until)

        # Generate trend data
        commits = self.git.get_commits(since=since, until=until)

        # Group by day
        trend_by_day: dict[datetime, int] = {}
        for commit in commits:
            day = commit.author_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            trend_by_day[day] = trend_by_day.get(day, 0) + 1

        trend_data = sorted(trend_by_day.items())

        return VelocityDashboard(
            period_start=since,
            period_end=until,
            commit_metrics=commit_metrics,
            branch_metrics=branch_metrics,
            merge_metrics=merge_metrics,
            trend_data=trend_data,
        )

    def close(self) -> None:
        """Close storage connection."""
        self.storage.close()
