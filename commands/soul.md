---
description: Generate a soul.md snapshot — your profile, patterns, and insights
allowed-tools: ["Bash", "Read", "Write"]
---

# Generate Soul Snapshot

Generate a living profile document that combines the user's explicit identity with derived insights from their usage data.

## Step 1: Read Explicit Profile

Query all explicit profile data:
```sql
SELECT category, key, value FROM user_profile WHERE source = 'explicit' ORDER BY category, key;
```

Also read the user's name for use throughout:
```sql
SELECT value FROM user_profile WHERE category = 'identity' AND key = 'name';
```

## Step 2: Check Installed Modules

```sql
SELECT name FROM modules WHERE enabled = 1;
```

This determines which derived queries to run.

## Step 3: Derive Insights from Usage Data

Run these queries against `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db` and collect the results.

### Core Stats (always available)

```sql
-- Platform age
SELECT MIN(created_at) as first_activity FROM activity_log;

-- Contact stats
SELECT COUNT(*) as total_contacts FROM contacts;
SELECT name, company FROM contacts ORDER BY updated_at DESC LIMIT 5;

-- Activity volume (last 30 days)
SELECT COUNT(*) as recent_actions FROM activity_log WHERE created_at > datetime('now', '-30 days');

-- Weekly activity trend (last 8 weeks)
SELECT strftime('%Y-W%W', created_at) as week, COUNT(*) as actions
FROM activity_log
WHERE created_at > datetime('now', '-56 days')
GROUP BY week ORDER BY week;
```

### If Project Tracker installed:
```sql
SELECT COUNT(*) as total_projects FROM projects;
SELECT COUNT(*) as active_projects FROM projects WHERE status IN ('active', 'in_progress');
SELECT COUNT(*) as completed_projects FROM projects WHERE status = 'completed';
```

### If Conversation Intelligence installed:
```sql
-- Average talk ratio across transcripts
SELECT AVG(talk_ratio) as avg_talk_ratio
FROM conversation_metrics WHERE talk_ratio IS NOT NULL;

-- Commitment follow-through
SELECT
  COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
  COUNT(*) as total
FROM commitments WHERE is_user_commitment = 1;

-- Total transcripts
SELECT COUNT(*) as total_transcripts FROM transcripts;
```

### If Journal installed:
```sql
-- Average energy
SELECT AVG(CAST(energy AS REAL)) as avg_energy FROM journal_entries WHERE energy IS NOT NULL;

-- Dominant mood
SELECT mood, COUNT(*) as count FROM journal_entries WHERE mood IS NOT NULL GROUP BY mood ORDER BY count DESC LIMIT 3;

-- Journaling frequency (entries per week, last 8 weeks)
SELECT COUNT(*) * 1.0 / 8 as entries_per_week FROM journal_entries WHERE created_at > datetime('now', '-56 days');
```

### If Decision Log installed:
```sql
-- Decision success rate
SELECT
  COUNT(CASE WHEN outcome_quality >= 4 THEN 1 END) as successful,
  COUNT(CASE WHEN outcome_quality IS NOT NULL THEN 1 END) as rated,
  COUNT(*) as total
FROM decisions;
```

### If Gmail installed:
```sql
SELECT COUNT(*) as total_emails FROM emails;
SELECT COUNT(DISTINCT contact_id) as email_contacts FROM emails WHERE contact_id IS NOT NULL;
```

## Step 4: Store Derived Values

For each derived metric, upsert into `user_profile` with `source='derived'` and an `evidence` explanation:

```sql
INSERT OR REPLACE INTO user_profile (category, key, value, source, evidence, updated_at)
VALUES ('stats', '<key>', '<value>', 'derived', '<how it was calculated>', datetime('now'));
```

Example keys: `total_contacts`, `platform_age_days`, `active_projects`, `avg_talk_ratio`, `commitment_follow_through`, `avg_energy`, `dominant_mood`, `decision_success_rate`, `weekly_activity_avg`.

**Only store values you actually calculated. Never fabricate or estimate.**

## Step 5: Generate soul.md

Write to `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/output/soul.md` with this structure:

```markdown
# Soul — [Name]
> Generated [date]. Powered by Software of You.

## Identity
- **Name:** ...
- **Role:** ...
- **Focus:** ...
- **Communication style:** ...

(Only include fields that have values)

## By the Numbers
| Metric | Value |
|--------|-------|
| Platform age | ... |
| Contacts | ... |
| Projects | ... (if module installed) |
| Transcripts | ... (if module installed) |
| ... | ... |

(Skip rows with no data)

## Patterns & Insights

### Communication (if conversation-intelligence installed and has data)
- Talk ratio: X% (you talk [more/less] than average)
- Commitment follow-through: X/Y completed (Z%)

### Energy & Mood (if journal installed and has data)
- Average energy: X/5
- Dominant moods: ...
- Journaling pace: X entries/week

### Decision-Making (if decision-log installed and has data)
- X decisions logged, Y rated
- Success rate: Z%

### Activity (always, if data exists)
- Average X actions/week over the last 8 weeks
- Trend: [increasing/stable/decreasing]

## Top Connections
(List top 5 most active contacts with company if available)

## What's Missing
(List modules not installed or data gaps — e.g., "No journal entries yet", "Decision log has no outcomes recorded")
```

**Rules:**
- Skip entire sections if no data exists for them
- Use human-readable numbers ("3 months" not "91 days", "about 60%" not "59.73%")
- The "What's Missing" section is encouraging, not critical — frame gaps as opportunities

## Step 6: Log and Update Metadata

```sql
INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('soul_last_generated', datetime('now'), datetime('now'));
```

Log to activity_log:
```sql
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
VALUES ('user_profile', 0, 'soul_generated', 'Generated soul.md snapshot', datetime('now'));
```

## Step 7: Present

Open the file with `open` and tell the user:
- Brief summary of what the snapshot contains
- When it was last generated before this (if ever)
- Suggest running `/soul` monthly to track how patterns evolve
