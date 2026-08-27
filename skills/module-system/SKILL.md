---
name: module-system
description: Use when checking which modules are installed, resolving cross-module features, or handling module-aware queries. This skill explains how modules discover each other and activate enhanced features.
---

# Module System

Software of You uses a modular architecture where each module adds domain-specific functionality, and modules automatically enhance each other when both are present.

## When to Use

- Before running any command that might use module-specific tables
- When generating summaries that could include cross-module data
- When a user asks about a feature that requires a specific module

## Module Detection

The `modules` table is the **source of truth** for what's installed:

```sql
SELECT name, version, enabled FROM modules WHERE enabled = 1;
```

Currently: crm, project-tracker, gmail, calendar, conversation-intelligence, decision-log, journal, notes, user-profile, slack.

Some modules also ship a `modules/{name}/manifest.json` with enhancement metadata, but many do not — only crm, project-tracker, gmail, calendar, conversation-intelligence, notes, and user-profile have manifest dirs (decision-log, journal, and slack have none). **Manifest reading is supplementary. Never assume a manifest exists** — trust the `modules` table, and read a manifest only after confirming its file is present.

## Cross-Module Enhancement Rules

When both **CRM and Project Tracker** are installed, four enhancements activate:

1. Contact views include the contact's projects.
2. Project views include client context (contact details + recent interactions).
3. Search spans contacts, projects, and tasks.
4. The activity log resolves entity names across whichever module owns each type.

The **canonical spec for these rules lives in the "Module Awareness" section of the project's CLAUDE.md** — follow that for the exact queries and behavior; the list above is just a summary.

## Cross-Referencing Beyond CRM + Project Tracker

Cross-module linkage now extends past that pair. Contacts are the hub, and several modules link back to them:

- **Emails and calendar events** link to contacts by email-address match (`emails.contact_id`, `calendar_events.contact_ids`).
- **Transcripts** link to contacts via `transcript_participants` (and carry commitments, metrics, and insights per contact).
- **Slack messages** link to contacts via `slack_messages.contact_id`.

When both sides of any such link are present, fold the related data into the entity's summary — `v_contact_health` already aggregates email, interaction, transcript, and Slack activity per contact.

## When a Module is NOT Installed

- Never reference its tables (they won't exist — the query will error)
- Never show features that depend on it
- Optionally hint: "You could see [feature] if you add the [module name] module."
- Handle gracefully — the experience should feel complete with whatever modules are present

## Adding Future Modules

New modules follow this pattern:
1. Migration `.sql` in `data/migrations/` creating module tables and registering the module via `INSERT OR REPLACE INTO modules`
2. Command `.md` files in `commands/` for module-specific slash commands
3. Optionally a `manifest.json` in `modules/{name}/` declaring features and enhancements

The SessionStart hook auto-detects new modules and runs their migrations.
