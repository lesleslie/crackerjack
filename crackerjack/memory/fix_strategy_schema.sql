-- Fix Strategy Memory Database Schema
-- Stores all fix attempts with neural embeddings for pattern learning

-- Table: Fix attempts with issue embeddings
CREATE TABLE IF NOT EXISTS fix_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_type TEXT NOT NULL,
    issue_message TEXT NOT NULL,
    file_path TEXT,
    stage TEXT,
    issue_embedding BLOB NOT NULL,  -- Packed 384-dim float array (neural)
    tfidf_vector BLOB,  -- TF-IDF sparse matrix (fallback)
    agent_used TEXT NOT NULL,
    strategy TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    confidence REAL,
    timestamp TEXT NOT NULL,
    session_id TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_fix_attempts_type ON fix_attempts(issue_type, success);
CREATE INDEX IF NOT EXISTS idx_fix_attempts_agent ON fix_attempts(agent_used, success);
CREATE INDEX IF NOT EXISTS idx_fix_attempts_timestamp ON fix_attempts(timestamp DESC);

-- Table: Strategy effectiveness summary (materialized view)
CREATE TABLE IF NOT EXISTS strategy_effectiveness (
    agent_strategy TEXT PRIMARY KEY,  -- "agent:strategy" composite key
    total_attempts INTEGER DEFAULT 0,
    successful_attempts INTEGER DEFAULT 0,
    success_rate REAL,
    last_attempted TEXT,
    last_successful TEXT
);

-- Trigger to auto-update effectiveness after insert
CREATE TRIGGER IF NOT EXISTS update_strategy_effectiveness_after_insert
AFTER INSERT ON fix_attempts
BEGIN
    INSERT OR REPLACE INTO strategy_effectiveness (agent_strategy, total_attempts, successful_attempts, success_rate, last_attempted, last_successful)
    SELECT
        agent_strategy,
        total_attempts + 1,
        successful_attempts + (CASE WHEN NEW.success THEN 1 ELSE 0 END),
        CAST(successful_attempts + (CASE WHEN NEW.success THEN 1 ELSE 0 END) AS REAL) / (total_attempts + 1),
        NEW.timestamp,
        CASE WHEN NEW.success THEN NEW.timestamp ELSE last_successful END
    FROM strategy_effectiveness
    WHERE agent_strategy = NEW.agent_used || ':' || NEW.strategy;
END;
