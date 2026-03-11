-- Telegram dev sessions: track remote Claude Code sessions spawned via /dev
CREATE TABLE IF NOT EXISTS telegram_dev_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    project_id INTEGER REFERENCES projects(id),
    project_name TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    instruction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'timeout', 'killed')),
    model TEXT NOT NULL DEFAULT 'sonnet',
    pid INTEGER,
    stdout_path TEXT,
    output_summary TEXT,
    git_diff_stat TEXT,
    git_before_sha TEXT,
    exit_code INTEGER,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    duration_seconds INTEGER,
    telegram_chat_id TEXT,
    branch_name TEXT,
    preview_url TEXT,
    deploy_status TEXT DEFAULT NULL
        CHECK (deploy_status IS NULL OR deploy_status IN ('deploying', 'deployed', 'deploy_failed')),
    deploy_pid INTEGER,
    deploy_stdout_path TEXT,
    review_status TEXT DEFAULT NULL
        CHECK (review_status IS NULL OR review_status IN ('pending', 'approved', 'rejected'))
);
CREATE INDEX IF NOT EXISTS idx_tg_dev_status ON telegram_dev_sessions(status);
CREATE INDEX IF NOT EXISTS idx_tg_dev_started ON telegram_dev_sessions(started_at);
