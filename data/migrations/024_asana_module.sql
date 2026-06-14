-- Asana Module Schema v1
-- Mirrors Asana workspaces, projects, tasks, and users into the local DB.
-- Auto-links assignees to contacts by email.

CREATE TABLE IF NOT EXISTS asana_workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    is_organization INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS asana_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gid TEXT UNIQUE NOT NULL,
    workspace_gid TEXT,
    name TEXT,
    email TEXT,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    is_self INTEGER NOT NULL DEFAULT 0,
    photo_url TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_asana_users_contact ON asana_users(contact_id);
CREATE INDEX IF NOT EXISTS idx_asana_users_email ON asana_users(email);
CREATE INDEX IF NOT EXISTS idx_asana_users_workspace ON asana_users(workspace_gid);

CREATE TABLE IF NOT EXISTS asana_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gid TEXT UNIQUE NOT NULL,
    workspace_gid TEXT NOT NULL,
    name TEXT NOT NULL,
    notes TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    owner_gid TEXT,
    color TEXT,
    due_on TEXT,
    modified_at TEXT,
    created_at TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_asana_projects_workspace ON asana_projects(workspace_gid);
CREATE INDEX IF NOT EXISTS idx_asana_projects_archived ON asana_projects(archived);

CREATE TABLE IF NOT EXISTS asana_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gid TEXT UNIQUE NOT NULL,
    workspace_gid TEXT NOT NULL,
    project_gid TEXT,                          -- primary project (first membership)
    project_gids TEXT,                         -- JSON array of all project memberships
    name TEXT NOT NULL,
    notes TEXT,
    assignee_gid TEXT,
    assignee_contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    created_by_gid TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    due_on TEXT,                               -- date only (YYYY-MM-DD)
    due_at TEXT,                               -- datetime if specific time set
    start_on TEXT,
    parent_gid TEXT,                           -- for subtasks
    num_subtasks INTEGER DEFAULT 0,
    permalink TEXT,
    custom_fields TEXT,                        -- JSON blob
    tags TEXT,                                 -- JSON array of {gid,name}
    modified_at TEXT NOT NULL,
    created_at TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_asana_tasks_project ON asana_tasks(project_gid);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_workspace ON asana_tasks(workspace_gid);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_assignee ON asana_tasks(assignee_gid);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_assignee_contact ON asana_tasks(assignee_contact_id);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_created_by ON asana_tasks(created_by_gid);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_due ON asana_tasks(due_on);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_completed ON asana_tasks(completed);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_modified ON asana_tasks(modified_at);
CREATE INDEX IF NOT EXISTS idx_asana_tasks_parent ON asana_tasks(parent_gid);

-- Manual linkage: a soy project may point to one Asana project for cross-references
ALTER TABLE projects ADD COLUMN linked_asana_project_gid TEXT;

CREATE INDEX IF NOT EXISTS idx_projects_linked_asana ON projects(linked_asana_project_gid);

-- Register module
INSERT OR REPLACE INTO modules (name, version) VALUES ('asana', '1.0.0');
