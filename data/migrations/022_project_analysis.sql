-- Project Analysis Module
-- AI-powered feature ideation, bug/security forecasting, and recommendations.
-- Each analysis run produces one project_analyses row + N project_analysis_items rows.
-- Items can be converted to real tasks via the server API.

CREATE TABLE IF NOT EXISTS project_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    summary TEXT,
    feature_ideas JSON,
    bug_forecasts JSON,
    recommendations JSON,
    data_snapshot JSON,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_analysis_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES project_analyses(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('feature_idea', 'bug_forecast', 'recommendation')),
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    likelihood TEXT CHECK (likelihood IN ('low', 'medium', 'high')),
    area TEXT,
    rationale TEXT,
    grounded_in TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'converted', 'dismissed')),
    converted_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_analyses_project ON project_analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_project_analysis_items_analysis ON project_analysis_items(analysis_id);
CREATE INDEX IF NOT EXISTS idx_project_analysis_items_project ON project_analysis_items(project_id);
CREATE INDEX IF NOT EXISTS idx_project_analysis_items_status ON project_analysis_items(status);
