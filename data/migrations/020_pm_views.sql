-- PM Computed Views — Per-project conversation intelligence stats
-- Used by: /pm-report, /dashboard, /project-page

-- ===================================================================
-- v_pm_overview: Per-project PM conversation stats
-- Aggregates conversation count, message totals, intelligence extracts
-- ===================================================================

DROP VIEW IF EXISTS v_pm_overview;
CREATE VIEW IF NOT EXISTS v_pm_overview AS
SELECT
    p.id AS project_id,
    p.name AS project_name,
    COUNT(pc.id) AS conversation_count,
    COALESCE(SUM(pc.message_count), 0) AS total_messages,
    MAX(pc.occurred_at) AS latest_conversation_at,
    CASE WHEN MAX(pc.occurred_at) IS NOT NULL
        THEN CAST(julianday('now') - julianday(MAX(pc.occurred_at)) AS INTEGER)
        ELSE NULL
    END AS days_since_last_pm,
    COALESCE(SUM(
        CASE WHEN pc.intelligence IS NOT NULL
            THEN json_array_length(json_extract(pc.intelligence, '$.decisions'))
            ELSE 0
        END
    ), 0) AS total_decisions,
    COALESCE(SUM(
        CASE WHEN pc.intelligence IS NOT NULL
            THEN json_array_length(json_extract(pc.intelligence, '$.action_items'))
            ELSE 0
        END
    ), 0) AS total_action_items,
    COALESCE(SUM(
        CASE WHEN pc.intelligence IS NOT NULL
            THEN json_array_length(json_extract(pc.intelligence, '$.claude_prompts'))
            ELSE 0
        END
    ), 0) AS total_claude_prompts,
    COALESCE(SUM(
        CASE WHEN pc.intelligence IS NOT NULL
            THEN json_array_length(json_extract(pc.intelligence, '$.architecture_notes'))
            ELSE 0
        END
    ), 0) AS total_architecture_notes,
    SUM(CASE WHEN pc.processed_at IS NOT NULL THEN 1 ELSE 0 END) AS processed_count,
    SUM(CASE WHEN pc.processed_at IS NULL THEN 1 ELSE 0 END) AS unprocessed_count
FROM projects p
LEFT JOIN pm_conversations pc ON pc.project_id = p.id
GROUP BY p.id;
