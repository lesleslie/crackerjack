-- Git Metrics Time-Series Storage Schema
-- Stores git analytics metrics for cross-project intelligence
-- Supports high-performance concurrent writes via Dhruva SQLite backend

-- Table: Git metrics time-series data
CREATE TABLE IF NOT EXISTS git_metrics (
    timestamp TIMESTAMP NOT NULL,
    repository_path TEXT NOT NULL,
    metric_type TEXT NOT NULL,  -- 'commit_velocity', 'branch_switches', 'merge_conflicts', etc.
    value REAL NOT NULL,
    metadata TEXT           -- JSON for flexible attributes
    PRIMARY KEY (repository_path, timestamp, metric_type)
);

-- Indexes for time-series queries
CREATE INDEX idx_git_metrics_repo_time ON git_metrics(repository_path, timestamp DESC);
CREATE INDEX idx_git_metrics_type ON git_metrics(metric_type);

-- Table: Git events log (detailed)
CREATE TABLE IF NOT EXISTS git_events (
    repository_path TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'commit', 'push', 'branch_create', 'branch_delete', 'merge', 'rebase', etc.
    timestamp TIMESTAMP NOT NULL,
    details TEXT NOT NULL
    PRIMARY KEY (repository_path, timestamp, event_type)
);

CREATE INDEX idx_git_events_repo_time ON git_events(repository_path, timestamp DESC);
CREATE INDEX idx_git_events_type ON git_events(event_type);

-- View: Latest metrics snapshot per repository
CREATE VIEW IF NOT EXISTS v_git_metrics_latest AS
SELECT
    repository_path,
    metric_type,
    value,
    metadata,
    timestamp
FROM git_metrics
WHERE (repository_path, timestamp, metric_type) IN (
    SELECT repository_path, MAX(timestamp), metric_type
    FROM git_metrics
    GROUP BY repository_path, metric_type
);
