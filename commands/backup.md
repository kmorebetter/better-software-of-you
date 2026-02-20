---
description: Export, import, or check backup status for all data
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: [export | import <path> | status]
---

# Backup

Manage full database backups for `${CLAUDE_PLUGIN_ROOT}/data/soy.db`.

Parse $ARGUMENTS to determine the subcommand. Default (no args) is **export**.

## /backup or /backup export

Export all data to a single JSON file.

1. Query every table and collect results as JSON arrays. Use `sqlite3 -json` mode for each table:

```
contacts, tags, entity_tags, notes, activity_log, modules, contact_interactions, contact_relationships, follow_ups, projects, tasks, milestones, emails, calendar_events, transcripts, transcript_participants, commitments, conversation_metrics, communication_insights, relationship_scores, generated_views, soy_meta
```

For tables that don't exist yet (module not installed), skip them — don't error.

2. Combine into a single JSON object keyed by table name:
```json
{
  "backup_date": "2026-02-19T...",
  "tables": {
    "contacts": [...],
    "projects": [...],
    ...
  }
}
```

3. Write to `${CLAUDE_PLUGIN_ROOT}/output/backup-{YYYY-MM-DD}.json` (use today's date).

4. Stamp the backup time in soy_meta:
```sql
INSERT OR REPLACE INTO soy_meta (key, value) VALUES ('last_backup_at', datetime('now'));
```

5. Report a summary: "Backup saved. X contacts, Y projects, Z emails exported." Include only non-empty table counts.

## /backup import <path>

Import data from a backup JSON file.

1. Read the JSON file at the provided path.
2. For each table in the backup (except `generated_views` — skip those, they are regenerated):
   - Use `INSERT OR REPLACE` to upsert every row.
   - Process tables in dependency order: modules first, then contacts, then everything else.
3. After import, log to activity_log:
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details)
VALUES ('system', 0, 'backup_imported', json_object('source', '<filename>', 'tables_imported', X));
```
4. Report what was imported with per-table counts: "Imported X contacts, Y projects, Z interactions from backup."

## /backup status

Show the last backup time and available backup files.

1. Check soy_meta for the last backup timestamp:
```sql
SELECT value FROM soy_meta WHERE key = 'last_backup_at';
```

2. List backup files in `${CLAUDE_PLUGIN_ROOT}/output/` matching `backup-*.json`, showing filename and size.

3. Present clearly: "Last backup: 3 days ago. 2 backup files found." If no backups exist, say so and suggest running `/backup`.
