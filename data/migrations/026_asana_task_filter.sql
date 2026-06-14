-- 026: Replace project→asana-project linkage with a name-based task filter.
-- Asana is organized by function (Clients, Site Health, Ops); soy projects are
-- deliverables. A keyword filter (e.g. "NASDAQ", "CPP") matches the right cluster
-- of Asana tasks across whichever Asana projects they happen to live in.

ALTER TABLE projects ADD COLUMN asana_task_filter TEXT;

CREATE INDEX IF NOT EXISTS idx_projects_asana_filter ON projects(asana_task_filter);

-- View: every Asana task matching a soy project's filter.
DROP VIEW IF EXISTS v_project_asana_tasks;
CREATE VIEW IF NOT EXISTS v_project_asana_tasks AS
SELECT
  p.id AS soy_project_id,
  p.name AS soy_project_name,
  p.asana_task_filter AS filter,
  at.gid AS task_gid,
  at.name AS task_name,
  at.completed,
  at.completed_at,
  at.due_on,
  at.assignee_gid,
  at.assignee_contact_id,
  at.created_by_gid,
  at.permalink,
  ap.gid AS asana_project_gid,
  ap.name AS asana_project_name,
  aw.name AS workspace_name
FROM projects p
JOIN asana_tasks at
  ON p.asana_task_filter IS NOT NULL
 AND p.asana_task_filter != ''
 AND at.name LIKE '%' || p.asana_task_filter || '%'
LEFT JOIN asana_projects ap ON ap.gid = at.project_gid
LEFT JOIN asana_workspaces aw ON aw.gid = at.workspace_gid;
