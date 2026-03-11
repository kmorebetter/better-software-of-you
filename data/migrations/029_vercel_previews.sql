-- Columns now included in 028_telegram_dev_sessions.sql.
-- These ALTERs remain for existing databases that created the table from the old 028.
-- They will harmlessly fail (duplicate column) on new installs — bootstrap suppresses errors.
ALTER TABLE telegram_dev_sessions ADD COLUMN branch_name TEXT;
ALTER TABLE telegram_dev_sessions ADD COLUMN preview_url TEXT;
ALTER TABLE telegram_dev_sessions ADD COLUMN deploy_status TEXT DEFAULT NULL
    CHECK (deploy_status IS NULL OR deploy_status IN ('deploying', 'deployed', 'deploy_failed'));
ALTER TABLE telegram_dev_sessions ADD COLUMN deploy_pid INTEGER;
ALTER TABLE telegram_dev_sessions ADD COLUMN deploy_stdout_path TEXT;
ALTER TABLE telegram_dev_sessions ADD COLUMN review_status TEXT DEFAULT NULL
    CHECK (review_status IS NULL OR review_status IN ('pending', 'approved', 'rejected'));
