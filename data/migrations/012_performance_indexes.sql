-- Performance indexes for commonly joined/filtered columns
CREATE INDEX IF NOT EXISTS idx_commitments_task ON commitments(linked_task_id);
CREATE INDEX IF NOT EXISTS idx_commitments_project ON commitments(linked_project_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON contact_interactions(type);
CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_address);
