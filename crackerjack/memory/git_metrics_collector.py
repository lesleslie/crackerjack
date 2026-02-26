from __future__ import annotations

import logging
import operator
import re
import sqlite3
import subprocess
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from crackerjack.models.protocols import SecureSubprocessExecutorProtocol

logger = logging.getLogger(__name__)


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
    branch_name: str
    event_type: t.Literal["created", "deleted", "checkout"]
    timestamp: datetime
    commit_hash: str | None = None


@dataclass(frozen=True)
class MergeEvent:
    merge_hash: str
    merge_timestamp: datetime
    merge_type: t.Literal["merge", "rebase", "cherry-pick"]
    source_branch: str | None
    target_branch: str | None
    has_conflicts: bool
    conflict_files: list[str] = field(default_factory=list)


@dataclass
class CommitMetrics:
    total_commits: int
    conventional_commits: int
    conventional_compliance_rate: float
    breaking_changes: int
    avg_commits_per_hour: float
    avg_commits_per_day: float
    avg_commits_per_week: float
    most_active_hour: int
    most_active_day: int
    time_period: timedelta


@dataclass
class BranchMetrics:
    total_branches: int
    active_branches: int
    branch_switches: int
    branches_created: int
    branches_deleted: int
    avg_branch_lifetime_hours: float
    most_switched_branch: str | None


@dataclass
class MergeMetrics:
    total_merges: int
    total_rebases: int
    total_conflicts: int
    conflict_rate: float
    avg_files_per_conflict: float
    most_conflicted_files: list[tuple[str, int]]
    merge_success_rate: float


@dataclass
class VelocityDashboard:
    period_start: datetime
    period_end: datetime
    commit_metrics: CommitMetrics
    branch_metrics: BranchMetrics
    merge_metrics: MergeMetrics
    trend_data: list[tuple[datetime, int]]


class _ConventionalCommitParser:
    PATTERN = re.compile(
        r"""^
        (?P<type>[a-z]+)
        (?:\((?P<scope>[^)]+)\))?
        (?P<breaking>!)?
        :\s*
        (?P<subject>.+?)
        (?:\n\n.+)?
        $""",
        re.VERBOSE | re.MULTILINE,
    )

    BREAKING_PATTERN = re.compile(
        r"""^BREAKING\sCHANGE:\s+(.+)$""",
        re.MULTILINE,
    )

    @classmethod
    def parse(cls, commit_message: str) -> tuple[bool, str | None, str | None, bool]:
        match = cls.PATTERN.search(commit_message)
        if not match:
            if cls.BREAKING_PATTERN.search(commit_message):
                return False, None, None, True
            return False, None, None, False

        commit_type = match.group("type")
        scope = match.group("scope")
        breaking_indicator = match.group("breaking") is not None

        has_breaking = (
            breaking_indicator
            or cls.BREAKING_PATTERN.search(commit_message) is not None
        )

        is_conventional = commit_type in CONVENTIONAL_TYPES

        return is_conventional, commit_type, scope, has_breaking


class _GitRepository:
    def __init__(
        self, repo_path: Path, executor: SecureSubprocessExecutorProtocol
    ) -> None:
        self.repo_path = repo_path.resolve()
        self.executor = executor

        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _git_command(
        self,
        args: list[str],
        timeout: float = 30.0,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
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

        cmd = [
            "log",
            "--pretty=format:%H|%ai|%an|%ae|%s",
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

                timestamp = datetime.fromisoformat(timestamp_str)

                is_merge = message.startswith("Merge ")

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
        cmd = ["branch", "-vv", "--format=%(refname: short)%09%(objectname)"]
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

                commit_hash, ref, selector = (
                    parts[0],
                    parts[1],
                    parts[2] if len(parts) > 2 else "",
                )

                timestamp_match = re.search(r"\{(.+?)\}", ref)
                if not timestamp_match:
                    continue

                timestamp_str = timestamp_match.group(1)
                timestamp = datetime.strptime(
                    timestamp_str.split("+")[0].strip(),
                    "%Y-%m-%d %H:%M:%S",
                )

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

                source_branch: str | None = None
                target_branch: str | None = None

                merge_match = re.search(r"Merge branch ['\"](.+?)['\"]", message)
                if merge_match:
                    source_branch = merge_match.group(1)

                pr_match = re.search(r"Merge pull request #\d+ from (.+?)", message)
                if pr_match:
                    source_branch = pr_match.group(1).split("/")[-1]

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

        cmd = ["show", "--pretty=%P", "--no-patch", merge_hash]
        result = self._git_command(cmd, timeout=10.0)

        parents = result.stdout.strip().split()
        return len(parents) >= 2

    def _get_conflict_files(self, merge_hash: str) -> list[str]:

        cmd = ["diff", "--name-only", f"{merge_hash}^1", f"{merge_hash}^2"]
        result = self._git_command(cmd, timeout=10.0, check=False)

        return result.stdout.strip().split("\n") if result.stdout.strip() else []


class GitMetricsStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

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

    def get_repository_health(self, repo_path: Path | str) -> dict[str, t.Any]:
        repo_name = Path(repo_path).name

        cursor = self.conn.execute(
            """
            SELECT
                COUNT(CASE WHEN datetime(recorded_at) < datetime('now', '-30 days') THEN 1 END) as stale_count,
                MAX(recorded_at) as last_activity
            FROM commits
            WHERE repo_name = ?
            """,
            (repo_name,),
        )
        row = cursor.fetchone()

        stale_count = row[0] if row else 0
        last_activity = row[1] if row else None

        total_commits = self.conn.execute(
            "SELECT COUNT(*) FROM commits WHERE repo_name = ?", (repo_name,)
        ).fetchone()[0]

        health_score = 50.0
        if total_commits > 0:
            recency_bonus = 20 if last_activity else 0
            activity_score = min(30, total_commits)
            health_score = 50 + recency_bonus + activity_score

        return {
            "health_score": health_score,
            "stale_branches": [],
            "unmerged_prs": 0,
            "large_files": [],
            "last_activity_timestamp": last_activity,
        }

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None


class GitMetricsCollector:
    def __init__(
        self,
        repo_path: Path,
        executor: SecureSubprocessExecutorProtocol,
        storage_path: Path | None = None,
    ) -> None:
        self.repo_path = repo_path.resolve()
        self.executor = executor

        self.git = _GitRepository(self.repo_path, self.executor)

        if storage_path is None:
            storage_path = self.repo_path / ".git" / "git_metrics.db"
        self.storage = GitMetricsStorage(storage_path)

        logger.info(f"GitMetricsCollector initialized for {self.repo_path}")

    def collect_commit_metrics(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> CommitMetrics:
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

        total_commits = len(commits)
        conventional_commits = sum(1 for c in commits if c.is_conventional)
        breaking_changes = sum(1 for c in commits if c.has_breaking_change)

        compliance_rate = (
            conventional_commits / total_commits if total_commits > 0 else 0.0
        )

        time_period = until - since
        hours = max(time_period.total_seconds() / 3600, 1.0)
        days = max(time_period.total_seconds() / 86400, 1.0)
        weeks = max(days / 7, 1.0)

        avg_commits_per_hour = total_commits / hours
        avg_commits_per_day = total_commits / days
        avg_commits_per_week = total_commits / weeks

        hour_counts: dict[int, int] = {}
        day_counts: dict[int, int] = {}

        for commit in commits:
            hour = commit.author_timestamp.hour
            day = commit.author_timestamp.weekday()

            hour_counts[hour] = hour_counts.get(hour, 0) + 1
            day_counts[day] = day_counts.get(day, 0) + 1

        most_active_hour = max(hour_counts, key=hour_counts.get) if hour_counts else 0
        most_active_day = max(day_counts, key=day_counts.get) if day_counts else 0

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
        if since is None:
            since = datetime.now() - timedelta(days=7)

        branches = self.git.get_branches()
        total_branches = len(branches)

        events = self.git.get_reflog_events(since=since)

        self.storage.store_branch_events(events)

        branch_switches = sum(1 for e in events if e.event_type == "checkout")
        branches_created = sum(1 for e in events if e.event_type == "created")
        branches_deleted = sum(1 for e in events if e.event_type == "deleted")

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

        active_branches = len(branch_switch_counts)

        avg_lifetime_hours = 0.0

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
        if since is None:
            since = datetime.now() - timedelta(days=30)
        if until is None:
            until = datetime.now()

        merge_events = self.git.get_merge_history(since=since, until=until)

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

        conflict_events = [e for e in merge_events if e.has_conflicts]
        if conflict_events:
            total_files = sum(len(e.conflict_files) for e in conflict_events)
            avg_files = total_files / len(conflict_events)
        else:
            avg_files = 0.0

        file_conflict_counts: dict[str, int] = {}
        for event in merge_events:
            for file_path in event.conflict_files:
                file_conflict_counts[file_path] = (
                    file_conflict_counts.get(file_path, 0) + 1
                )

        most_conflicted = sorted(
            file_conflict_counts.items(),
            key=operator.itemgetter(1),
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
        until = datetime.now()
        since = until - timedelta(days=days_back)

        commit_metrics = self.collect_commit_metrics(since=since, until=until)
        branch_metrics = self.collect_branch_activity(since=since)
        merge_metrics = self.collect_merge_patterns(since=since, until=until)

        commits = self.git.get_commits(since=since, until=until)

        trend_by_day: dict[datetime, int] = {}
        for commit in commits:
            day = commit.author_timestamp.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
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
        self.storage.close()
