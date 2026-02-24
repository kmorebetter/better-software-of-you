# Staleness Queries

Reference for `/build-all` incremental builds. Each query returns the most recent data modification timestamp for a given page type. Compare against `generated_views.updated_at` to determine if a page needs rebuilding.

**Core pattern:** `MAX()` across all timestamp columns from tables that feed into a page. If the max data timestamp is newer than the page's `updated_at`, the page is stale and needs rebuilding.

---

## Sidebar Staleness (Global Check — Run First)

If entity counts have changed since pages were last built, the sidebar on every page is wrong. This triggers a full rebuild.

```sql
SELECT
  (SELECT COUNT(*) FROM contacts WHERE status = 'active') as active_contacts,
  (SELECT COUNT(*) FROM generated_views WHERE view_type = 'entity_page' AND entity_type = 'contact') as contact_pages,
  (SELECT COUNT(*) FROM projects WHERE status IN ('active','planning')) as active_projects,
  (SELECT COUNT(*) FROM generated_views WHERE view_type = 'entity_page' AND entity_type = 'project') as project_pages;
```

**Stale if:** `active_contacts != contact_pages` OR `active_projects != project_pages`.

When sidebar is stale, mark ALL pages for rebuild — every page embeds the sidebar.

---

## Entity Page Staleness (Per Contact)

Returns the latest data modification timestamp across all tables that feed into a contact's entity page. Run once per active contact, substituting `?` with the contact's ID.

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM contacts WHERE id = ?
  UNION ALL SELECT MAX(synced_at) FROM emails WHERE contact_id = ?
  UNION ALL SELECT MAX(created_at) FROM contact_interactions WHERE contact_id = ?
  UNION ALL SELECT MAX(COALESCE(t.updated_at, t.created_at)) FROM transcripts t
    JOIN transcript_participants tp ON tp.transcript_id = t.id
    WHERE tp.contact_id = ?
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM commitments WHERE owner_contact_id = ?
  UNION ALL SELECT MAX(created_at) FROM follow_ups WHERE contact_id = ?
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM projects WHERE client_id = ?
  UNION ALL SELECT MAX(created_at) FROM notes WHERE entity_type = 'contact' AND entity_id = ?
  UNION ALL SELECT MAX(synced_at) FROM calendar_events WHERE contact_ids LIKE '%' || ? || '%'
  UNION ALL SELECT MAX(created_at) FROM relationship_scores WHERE contact_id = ?
  UNION ALL SELECT MAX(created_at) FROM communication_insights WHERE contact_id = ?
  UNION ALL SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'contact' AND entity_id = ?
);
```

**Compare against:** `generated_views.updated_at WHERE view_type = 'entity_page' AND entity_type = 'contact' AND entity_id = ?`

**Stale if:** `latest_data_change > page_updated_at`, OR page has never been generated, OR file missing from disk.

**Note:** `calendar_events.contact_ids` uses LIKE matching which may false-positive (id 1 matching 11). This only causes an unnecessary rebuild, never a missed one.

### Batch variant (check all contacts at once)

For efficiency during `/build-all`, run a single query that returns staleness per contact:

```sql
SELECT
  c.id,
  c.name,
  gv.filename,
  gv.updated_at as page_updated_at,
  MAX(data_ts) as latest_data_change,
  CASE WHEN gv.updated_at IS NULL THEN 1
       WHEN MAX(data_ts) > gv.updated_at THEN 1
       ELSE 0
  END as is_stale
FROM contacts c
LEFT JOIN generated_views gv
  ON gv.view_type = 'entity_page' AND gv.entity_type = 'contact' AND gv.entity_id = c.id
LEFT JOIN (
  SELECT contact_id as cid, MAX(ts) as data_ts FROM (
    SELECT id as contact_id, COALESCE(updated_at, created_at) as ts FROM contacts WHERE status = 'active'
    UNION ALL SELECT contact_id, synced_at FROM emails
    UNION ALL SELECT contact_id, created_at FROM contact_interactions
    UNION ALL SELECT tp.contact_id, COALESCE(t.updated_at, t.created_at)
      FROM transcripts t JOIN transcript_participants tp ON tp.transcript_id = t.id
    UNION ALL SELECT owner_contact_id, COALESCE(updated_at, created_at) FROM commitments WHERE owner_contact_id IS NOT NULL
    UNION ALL SELECT contact_id, created_at FROM follow_ups
    UNION ALL SELECT client_id, COALESCE(updated_at, created_at) FROM projects WHERE client_id IS NOT NULL
    UNION ALL SELECT entity_id, created_at FROM notes WHERE entity_type = 'contact'
    UNION ALL SELECT rs.contact_id, rs.created_at FROM relationship_scores rs
    UNION ALL SELECT ci.contact_id, ci.created_at FROM communication_insights ci
    UNION ALL SELECT CAST(entity_id AS INTEGER), created_at FROM activity_log WHERE entity_type = 'contact'
    UNION ALL SELECT CAST(ce.contact_ids AS INTEGER), ce.synced_at FROM calendar_events ce WHERE ce.contact_ids IS NOT NULL AND ce.contact_ids != ''
  ) GROUP BY contact_id
) d ON d.cid = c.id
WHERE c.status = 'active'
GROUP BY c.id
ORDER BY c.name;
```

---

## Project Page Staleness (Per Project)

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM projects WHERE id = ?
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM tasks WHERE project_id = ?
  UNION ALL SELECT MAX(created_at) FROM milestones WHERE project_id = ?
  UNION ALL SELECT MAX(created_at) FROM notes WHERE entity_type = 'project' AND entity_id = ?
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM contacts WHERE id = (SELECT client_id FROM projects WHERE id = ?)
  UNION ALL SELECT MAX(synced_at) FROM emails WHERE contact_id = (SELECT client_id FROM projects WHERE id = ?)
  UNION ALL SELECT MAX(synced_at) FROM calendar_events WHERE project_id = ?
  UNION ALL SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'project' AND entity_id = ?
);
```

**Compare against:** `generated_views.updated_at WHERE view_type = 'entity_page' AND entity_type = 'project' AND entity_id = ?`

---

## Transcript Page Staleness (Per Transcript)

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM transcripts WHERE id = ?
  UNION ALL SELECT MAX(created_at) FROM conversation_metrics WHERE transcript_id = ?
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM commitments WHERE transcript_id = ?
  UNION ALL SELECT MAX(created_at) FROM communication_insights WHERE transcript_id = ?
  UNION ALL SELECT MAX(COALESCE(c.updated_at, c.created_at))
    FROM contacts c JOIN transcript_participants tp ON tp.contact_id = c.id
    WHERE tp.transcript_id = ?
);
```

**Compare against:** `generated_views.updated_at WHERE view_type = 'transcript_page' AND entity_id = ?`

---

## Module View Staleness

Each module view depends on a small set of tables. One query per view.

### Contacts Index (`contacts.html`)

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM contacts
  UNION ALL SELECT MAX(created_at) FROM activity_log WHERE entity_type = 'contact'
  UNION ALL SELECT MAX(created_at) FROM relationship_scores
);
```

### Network Map (`network-map.html`)

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM contacts
  UNION ALL SELECT MAX(created_at) FROM contact_interactions
  UNION ALL SELECT MAX(created_at) FROM relationship_scores
);
```

### Email Hub (`email-hub.html`)

```sql
SELECT MAX(synced_at) as latest_data_change FROM emails;
```

### Week View (`week-view.html`)

```sql
SELECT MAX(synced_at) as latest_data_change FROM calendar_events;
```

### Conversations View (`conversations.html`)

```sql
SELECT MAX(ts) as latest_data_change FROM (
  SELECT MAX(COALESCE(updated_at, created_at)) as ts FROM transcripts
  UNION ALL SELECT MAX(COALESCE(updated_at, created_at)) FROM commitments
  UNION ALL SELECT MAX(created_at) FROM communication_insights
  UNION ALL SELECT MAX(created_at) FROM relationship_scores
  UNION ALL SELECT MAX(created_at) FROM conversation_metrics
);
```

### Decision Journal (`decision-journal.html`)

```sql
SELECT MAX(COALESCE(updated_at, created_at)) as latest_data_change FROM decisions;
```

### Journal View (`journal.html`)

```sql
SELECT MAX(COALESCE(updated_at, created_at)) as latest_data_change FROM journal_entries;
```

### Notes View (`notes.html`)

```sql
SELECT MAX(COALESCE(updated_at, created_at)) as latest_data_change FROM standalone_notes;
```

---

## Always-Rebuild Views

These views are NOT staleness-checked — they always rebuild:

| View | Reason |
|------|--------|
| Dashboard (`dashboard.html`) | Aggregates everything, is the landing page |
| Nudges (`nudges.html`) | Urgency-sensitive, shifts daily based on dates |
| Timeline (`timeline.html`) | Cross-module chronological, date-relative |
| Weekly Review (`weekly-review.html`) | Aggregated weekly lens, date-relative |
| Search Hub (`search.html`) | Embeds all data as JSON for client-side search |

---

## Staleness Decision Logic

A page needs rebuilding if ANY of these conditions are true:

1. **Force flag** — `/build-all force` was used
2. **Never built** — no row in `generated_views` for this page
3. **File missing** — row exists in `generated_views` but file doesn't exist on disk
4. **Sidebar stale** — entity count mismatch (triggers full rebuild)
5. **Data newer than page** — `latest_data_change > page_updated_at`
6. **Always-rebuild** — page is in the always-rebuild list (dashboard, cross-cutting views)

A page can be **skipped** only when ALL of these are true:
- Not force mode
- Row exists in `generated_views`
- File exists on disk
- Sidebar is not stale
- `latest_data_change <= page_updated_at`
- Not in the always-rebuild list
