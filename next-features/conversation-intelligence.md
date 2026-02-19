# Conversation Intelligence Module

**Status:** Spec
**Priority:** High
**Dependencies:** CRM module (required), Project Tracker (optional, enables commitment-to-task linking)

---

## Overview

A module that imports meeting transcripts, extracts commitments and follow-ups, and provides ongoing communication coaching grounded in what you actually said to real people. The value compounds over time — every conversation makes the relationship picture richer.

This is the feature that makes Software of You more than a personal CRM. It's a mirror for how you show up in your professional relationships.

---

## Design Principles

- **No API keys, no OAuth, no setup screens.** Non-technical users must be able to use this on day one.
- **Source-agnostic.** The analysis engine works on transcript text, not Fathom-specific data structures. Paste from anything.
- **Every call gets processed.** No batching, no weekly digests for the raw analysis. Process immediately on import.
- **Honest feedback.** The coach insight should reference specific moments from the call. Generic advice is useless.
- **Relationship-first.** Every metric and insight is contextualized by who you were talking to and your history with them.

---

## Import Strategy

### Tier 1: Paste-In (Launch)

User pastes a transcript and tells SOY who the call was with. SOY handles the rest.

Example interaction:
```
User: "Here's my call with Sarah from today"
[pastes transcript]

SOY: Processes transcript, maps speakers to contacts, extracts commitments,
     generates relationship pulse and coach insight.
```

**Parsing requirements:**
- Detect speaker labels (common formats: "Speaker 1:", "Sarah:", "[Sarah Chen]", timestamps with names)
- Map speakers to existing SOY contacts by name/fuzzy match
- Handle unknown speakers gracefully — ask user to identify or create new contact
- Extract meeting duration from timestamps if available
- Preserve raw transcript for re-analysis when models improve

### Tier 2: File Drop (Fast Follow)

User drops a `.txt`, `.md`, or `.vtt` file exported from their transcription tool. Same processing as paste-in but from file.

SOY watches no directories. User explicitly says "import this transcript" and provides the file.

### Tier 3: Fathom Integration (Later, Power Users)

Fathom API integration for automatic sync. Only pursue this after Tier 1 proves the analysis engine. Would require:
- Fathom API key (user provides once, SOY stores locally)
- Periodic sync or on-demand pull
- Automatic participant mapping

**Not a launch priority.** Paste-in covers 90% of the value with 10% of the complexity.

---

## Data Model

### New Tables

Migration: `data/migrations/004_conversation_intelligence_module.sql`

```sql
-- Conversation Intelligence Module
-- Imports meeting transcripts, extracts commitments, and provides communication coaching.

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,                          -- "Call with Sarah - Rebrand Discussion"
    source TEXT DEFAULT 'paste',         -- 'paste', 'file', 'fathom', 'otter', etc.
    raw_text TEXT NOT NULL,              -- Full transcript text, preserved for re-analysis
    summary TEXT,                        -- AI-generated summary
    duration_minutes INTEGER,            -- Extracted or estimated from timestamps
    occurred_at TEXT NOT NULL,           -- When the meeting happened
    processed_at TEXT,                   -- When SOY analyzed it
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcript_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
    contact_id INTEGER REFERENCES contacts(id),     -- NULL if unknown/unmatched speaker
    speaker_label TEXT NOT NULL,                     -- As it appears in transcript ("Speaker 1", "Sarah")
    is_user INTEGER DEFAULT 0,                       -- 1 = this is the SOY user themselves
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
    owner_contact_id INTEGER REFERENCES contacts(id),  -- Who made the commitment (NULL = the user)
    is_user_commitment INTEGER DEFAULT 0,               -- 1 = user committed to this, 0 = someone else did
    description TEXT NOT NULL,                           -- "Send the proposal draft by Friday"
    deadline_mentioned TEXT,                             -- Extracted deadline if any, human-readable
    deadline_date TEXT,                                  -- Parsed date if possible
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'completed', 'overdue', 'cancelled')),
    linked_task_id INTEGER,                             -- FK to tasks table if Project Tracker installed
    linked_project_id INTEGER,                          -- FK to projects table if applicable
    completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
    contact_id INTEGER REFERENCES contacts(id),        -- Per-participant metrics
    talk_ratio REAL,                                    -- 0.0 to 1.0, percentage of words spoken
    word_count INTEGER,
    question_count INTEGER,                             -- Questions asked by this participant
    interruption_count INTEGER,                         -- Times this participant interrupted others
    longest_monologue_seconds INTEGER,                  -- Longest unbroken speaking stretch
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS communication_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
    contact_id INTEGER REFERENCES contacts(id),         -- Primary contact this insight relates to
    insight_type TEXT NOT NULL CHECK(insight_type IN (
        'relationship_pulse',   -- Relationship context and trajectory
        'coach_note',           -- Single actionable coaching observation
        'pattern_alert'         -- Recurring pattern detected across multiple calls
    )),
    content TEXT NOT NULL,                               -- The insight text
    data_points TEXT,                                    -- JSON: supporting metrics/evidence
    sentiment TEXT CHECK(sentiment IN ('positive', 'neutral', 'needs_attention')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relationship_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    score_date TEXT NOT NULL,                            -- Date this score was calculated
    meeting_frequency REAL,                              -- Meetings per month (rolling)
    talk_ratio_avg REAL,                                 -- Average talk ratio across recent calls
    commitment_follow_through REAL,                      -- % of commitments completed on time (both directions)
    topic_diversity REAL,                                -- Range of topics discussed (0-1)
    relationship_depth TEXT CHECK(relationship_depth IN (
        'transactional', 'professional', 'collaborative', 'trusted'
    )),
    trajectory TEXT CHECK(trajectory IN (
        'strengthening', 'stable', 'cooling', 'at_risk'
    )),
    notes TEXT,                                          -- AI-generated context for this score
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transcripts_occurred_at ON transcripts(occurred_at);
CREATE INDEX IF NOT EXISTS idx_transcript_participants_transcript ON transcript_participants(transcript_id);
CREATE INDEX IF NOT EXISTS idx_transcript_participants_contact ON transcript_participants(contact_id);
CREATE INDEX IF NOT EXISTS idx_commitments_transcript ON commitments(transcript_id);
CREATE INDEX IF NOT EXISTS idx_commitments_owner ON commitments(owner_contact_id);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_conversation_metrics_transcript ON conversation_metrics(transcript_id);
CREATE INDEX IF NOT EXISTS idx_conversation_metrics_contact ON conversation_metrics(contact_id);
CREATE INDEX IF NOT EXISTS idx_communication_insights_transcript ON communication_insights(transcript_id);
CREATE INDEX IF NOT EXISTS idx_communication_insights_contact ON communication_insights(contact_id);
CREATE INDEX IF NOT EXISTS idx_communication_insights_type ON communication_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_relationship_scores_contact ON relationship_scores(contact_id);
CREATE INDEX IF NOT EXISTS idx_relationship_scores_date ON relationship_scores(score_date);

-- Register module
INSERT OR REPLACE INTO modules (name, version, installed_at, enabled)
VALUES ('conversation-intelligence', '1.0.0', datetime('now'), 1);
```

---

## Module Manifest

File: `modules/conversation-intelligence/manifest.json`

```json
{
  "name": "conversation-intelligence",
  "display_name": "Conversation Intelligence",
  "version": "1.0.0",
  "description": "Import meeting transcripts, extract commitments, and get communication coaching grounded in real conversations.",
  "migration": "004_conversation_intelligence_module.sql",
  "tables": [
    "transcripts",
    "transcript_participants",
    "commitments",
    "conversation_metrics",
    "communication_insights",
    "relationship_scores"
  ],
  "entities": ["transcript", "commitment", "insight"],
  "commands": ["/import-call", "/commitments", "/communication-review", "/relationship-pulse"],
  "standalone_features": [
    "Paste-in transcript import with speaker detection",
    "Commitment extraction (user and others)",
    "Per-call communication metrics",
    "Coach insight per conversation",
    "Relationship scoring over time"
  ],
  "enhancements": [
    {
      "requires_module": "crm",
      "features": [
        "Auto-map transcript speakers to CRM contacts",
        "Link commitments to existing follow-ups",
        "Enrich contact summaries with communication patterns",
        "Add conversation history to contact relationship view",
        "Communication trajectory in contact-summary command"
      ]
    },
    {
      "requires_module": "project-tracker",
      "features": [
        "Convert commitments to project tasks",
        "Link transcript discussions to active projects",
        "Flag recurring unresolved topics across meetings",
        "Include conversation context in project briefs"
      ]
    }
  ]
}
```

---

## Commands

### `/import-call`

**Purpose:** Import a meeting transcript and process it.

**Usage:**
```
/import-call                     → Prompts user to paste transcript
/import-call <filepath>          → Import from file
```

**Processing pipeline (what SOY does internally):**

1. **Parse transcript** — Detect speaker labels, timestamps, structure
2. **Identify participants** — Match speaker labels to existing contacts. Ask user to confirm or create new contacts for unknowns.
3. **Identify the user** — Ask which speaker is them (if not obvious from context)
4. **Generate title & summary** — From transcript content
5. **Extract commitments** — Things the user said they'd do. Things others said they'd do. Suggested follow-ups SOY infers from context.
6. **Calculate metrics** — Talk ratio, question count, interruptions, monologue length per participant
7. **Generate insights:**
   - **Relationship pulse** — Contextual read on the relationship, informed by history
   - **Coach note** — One specific, actionable observation from this call
   - **Pattern alert** (if applicable) — Recurring pattern detected across calls with this person
8. **Update relationship scores** — Recalculate trajectory for each participant
9. **Log activity** — Record the import and all generated data in activity_log

**Output to user:**
```
Call imported: "Rebrand Discussion with Sarah" (32 min)

Commitments:
  You → Send updated proposal by Friday
  You → Schedule follow-up with design team
  Sarah → Share brand guidelines doc

Relationship Pulse:
  6th meeting this quarter. Conversations have shifted from project logistics
  to team concerns — signals growing trust. Open commitment follow-through
  with Sarah is at 85%.

Coach's Note:
  You asked Sarah what worried her most about the timeline, then stayed
  quiet while she worked through it. That space led to the most productive
  part of the call. More of that.

Next: /commitments to see all open items, or /relationship-pulse Sarah for full history
```

### `/commitments`

**Purpose:** View and manage extracted commitments.

**Usage:**
```
/commitments                     → Show all open commitments
/commitments mine                → Just things you owe others
/commitments theirs              → Things others owe you
/commitments overdue             → Past deadline
/commitments <contact>           → Commitments involving specific person
/commitments complete <id>       → Mark commitment as done
```

**Cross-module (with Project Tracker):**
- Show option to convert commitment to task: "Want to add this to the Rebrand project as a task?"
- Flag commitments that duplicate existing tasks

### `/communication-review`

**Purpose:** Your communication assessment — relationship-focused, data-driven, with coaching.

**Usage:**
```
/communication-review            → This week's review across all conversations
/communication-review <contact>  → Review for specific relationship
/communication-review month      → Monthly trends
```

**Output structure:**

**Data Snapshot:**
- Calls this period, total time in meetings
- Average talk ratio across calls
- Questions asked vs. statements made
- Commitment follow-through rate

**Relationship Focus (per contact with calls this period):**
- Meeting cadence trend
- Tone/topic shifts from previous period
- Open commitments both directions
- Relationship trajectory: strengthening / stable / cooling / at risk

**Coach Summary:**
- Top pattern observed this period (e.g., "Your talk ratio has crept up to 65% across calls this week")
- One strength to keep doing
- One thing to try next week

### `/relationship-pulse`

**Purpose:** Deep view into a specific relationship, combining CRM data with conversation intelligence.

**Usage:**
```
/relationship-pulse <contact>    → Full relationship view
```

**Output combines:**
- CRM data (contact info, tags, notes, interaction history)
- Meeting frequency and trajectory
- Communication patterns over time (talk ratio trend, question quality)
- All open commitments both directions
- Topic evolution across conversations
- Relationship depth assessment
- Coach summary for this relationship specifically

This is the "how are things with Sarah?" command.

---

## Agent

File: `agents/conversation-agent.md`

**Purpose:** Specialized agent for transcript analysis. Handles the heavy lifting of parsing transcripts, extracting commitments, calculating metrics, and generating insights.

**Model:** Sonnet (fast enough for per-call processing, smart enough for nuanced coaching)

**Tools:** Bash (database access), Read

**Responsibilities:**
- Parse raw transcript text into structured speaker turns
- Fuzzy-match speaker labels to existing contacts
- Extract explicit and implicit commitments
- Calculate conversation metrics (talk ratio, questions, interruptions)
- Generate relationship pulse using historical context
- Generate coach note — must reference specific moments from the transcript
- Detect patterns across multiple conversations with same contact
- Update relationship scores

**Key instruction:** The coach note must never be generic. It must cite a specific moment, quote, or behavior from this transcript. If nothing notable happened, say so — don't manufacture insight.

---

## Skill Reference

File: `skills/conversation-intelligence/SKILL.md`

Should document:
- Transcript parsing patterns (speaker label formats, timestamp formats)
- Commitment extraction heuristics (language patterns that signal commitments)
- Metric calculation methods
- Insight generation guidelines
- Relationship scoring algorithm

File: `skills/conversation-intelligence/references/transcript-formats.md`

Should document:
- Fathom transcript format
- Otter transcript format
- Generic speaker-label formats
- VTT/SRT subtitle formats
- How to handle messy/inconsistent formatting

---

## Cross-Module Enhancements

### With CRM (required)

When a transcript is imported:
- `contact_interactions` gets a new entry (type: `meeting`, direction: `both`) linked to each participant
- `follow_ups` are created for extracted commitments with deadlines
- `/contact-summary` includes communication patterns and coach insights
- `/contact` detail view shows recent conversation metrics

### With Project Tracker (optional)

When a transcript is imported:
- SOY checks if any discussed topics match active project names/descriptions
- Offers to link commitments as tasks to relevant projects
- `/project-brief` includes recent conversation context about the project
- Pattern alerts flag topics discussed repeatedly without resolution ("You've discussed the database migration in 3 meetings without creating a task")

---

## Relationship Scoring Algorithm

Calculated after each transcript import. Stored in `relationship_scores` per contact.

**Inputs:**
- Meeting frequency (rolling 3-month window)
- Talk ratio balance (closer to 50/50 = healthier for collaborative relationships)
- Commitment follow-through rate (both directions)
- Topic diversity (range of subjects discussed)
- Trend direction (are metrics improving or declining?)

**Outputs:**

`relationship_depth`: Qualitative assessment
- **Transactional** — Focused exchanges, limited scope, low meeting frequency
- **Professional** — Regular contact, task-oriented, moderate depth
- **Collaborative** — Frequent, balanced conversations, shared problem-solving
- **Trusted** — High depth, personal topics mixed with professional, strong follow-through

`trajectory`: Direction of change
- **Strengthening** — Positive trend in frequency, balance, or depth
- **Stable** — No significant change
- **Cooling** — Declining frequency or increasing imbalance
- **At Risk** — Multiple negative signals (missed commitments, declining frequency, one-sided conversations)

**Recalculation:** After every new transcript involving that contact. Uses last 90 days of data.

---

## Dashboard View

Extend `/dashboard` and `/view` commands with conversation intelligence panels:

**Dashboard cards:**
- This week's calls (count, total minutes)
- Open commitments (yours / theirs)
- Relationships needing attention (trajectory = cooling or at_risk)
- Coach highlight of the week

**Dedicated view (`/view conversations`):**
- Recent transcripts with quick stats
- Commitment tracker (Kanban-style: open / overdue / completed)
- Relationship health grid (all active contacts with trajectory indicators)
- Communication trends chart (talk ratio, question count over time)

---

## Implementation Plan

### Phase 1: Foundation (Core Data + Paste Import)

**Build:**
1. Migration `004_conversation_intelligence_module.sql` — create all tables
2. Module manifest `modules/conversation-intelligence/manifest.json`
3. Update `hooks/session-start.py` to detect new module
4. Conversation agent (`agents/conversation-agent.md`) — transcript parsing and basic extraction
5. `/import-call` command — paste-in flow only
   - Speaker detection and contact mapping
   - Basic commitment extraction (explicit "I'll..." and "We'll..." patterns)
   - Summary generation
   - Activity logging
6. `/commitments` command — view and manage commitments

**Validate:** Import 3-5 real transcripts. Verify speaker mapping, commitment extraction accuracy, and data integrity.

### Phase 2: Communication Metrics + Coach Insight

**Build:**
1. Metric calculation in conversation agent — talk ratio, questions, interruptions, monologue length
2. `conversation_metrics` population during import
3. Coach note generation — specific, references actual moments from transcript
4. `communication_insights` storage (coach_note type)
5. Update `/import-call` output to include metrics and coach note

**Validate:** Import 5+ transcripts. Review coach notes for specificity — reject any that could apply to a generic meeting.

### Phase 3: Relationship Intelligence

**Build:**
1. Relationship pulse generation — contextual read using historical data
2. `communication_insights` storage (relationship_pulse type)
3. Relationship scoring algorithm and `relationship_scores` table population
4. Pattern detection across multiple calls with same contact
5. `communication_insights` storage (pattern_alert type)
6. `/relationship-pulse` command
7. `/communication-review` command

**Validate:** Need 3+ transcripts per contact to test trajectory detection. Verify scores feel accurate against intuition.

### Phase 4: Cross-Module Integration

**Build:**
1. CRM integration — auto-create `contact_interactions` on import, enrich `/contact-summary`
2. Project Tracker integration — commitment-to-task conversion, project mention detection
3. Update `/contact-summary` and `/project-brief` to include conversation intelligence data
4. Extend `/dashboard` with conversation intelligence cards
5. Build `/view conversations` dedicated view

**Validate:** Full workflow — import transcript, see it reflected in contact summary, convert commitment to task, view on dashboard.

### Phase 5: File Import + Polish

**Build:**
1. File import support in `/import-call` (.txt, .md, .vtt)
2. Transcript format detection and normalization
3. Skill reference documentation (`skills/conversation-intelligence/`)
4. Edge case handling — transcripts with unknown speakers, very short calls, one-on-one vs. group calls
5. Re-analysis capability — reprocess old transcripts when models improve

---

## Open Questions

1. **Group calls** — How to handle meetings with 3+ participants? Score each relationship separately? Generate a single coach note or one per relationship?

2. **Re-analysis trigger** — Should SOY offer to re-analyze old transcripts periodically? Or only on user request? ("Your oldest transcripts were analyzed 6 months ago — want me to re-analyze with current capabilities?")

3. **Commitment deduplication** — If the same commitment is mentioned across multiple meetings, should SOY merge them or track separately as evidence of non-completion?

4. **Sensitivity calibration** — Some users will want hard truths, some will want gentle nudges. Should there be a setting, or should SOY calibrate based on how the user responds to feedback?

5. **Historical import** — If a user has 50 old transcripts, should there be a bulk import flow? Or process one at a time?
