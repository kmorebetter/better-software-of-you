-- Software of You — Complete Schema Reference
-- This file is a reference copy. Actual migrations are in data/migrations/

-- === CORE (always present) ===

-- Platform metadata
-- soy_meta(key TEXT PK, value TEXT, updated_at TEXT)

-- Contacts
-- contacts(id INTEGER PK, name TEXT, email TEXT, phone TEXT, company TEXT,
--          role TEXT, type TEXT ['individual','company'],
--          status TEXT ['active','inactive','archived'],
--          notes TEXT, created_at TEXT, updated_at TEXT)

-- Tags
-- tags(id INTEGER PK, name TEXT UNIQUE, color TEXT, category TEXT)

-- Entity-tag links (polymorphic)
-- entity_tags(entity_type TEXT, entity_id INTEGER, tag_id INTEGER FK→tags)
--   PK: (entity_type, entity_id, tag_id)

-- Notes (polymorphic)
-- notes(id INTEGER PK, entity_type TEXT, entity_id INTEGER,
--       content TEXT, created_at TEXT)

-- Activity log (polymorphic)
-- activity_log(id INTEGER PK, entity_type TEXT, entity_id INTEGER,
--              action TEXT, details TEXT, created_at TEXT)

-- Module registry
-- modules(name TEXT PK, version TEXT, installed_at TEXT, enabled INTEGER)

-- Google Accounts (multi-account support)
-- google_accounts(id INTEGER PK, email TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
--   display_name TEXT, token_file TEXT NOT NULL,
--   is_primary INTEGER NOT NULL DEFAULT 0,
--   connected_at TEXT DEFAULT datetime('now'),
--   last_synced_at TEXT,
--   status TEXT ['active','disconnected','error'])
-- Tokens stored in ~/.local/share/software-of-you/tokens/<email>.json

-- User profile
-- user_profile(category TEXT, key TEXT, value TEXT, source TEXT, updated_at TEXT)
--   PK: (category, key)


-- === CRM MODULE ===

-- Contact interactions
-- contact_interactions(id INTEGER PK, contact_id INTEGER FK→contacts,
--   type TEXT ['email','call','meeting','message','other'],
--   direction TEXT ['inbound','outbound'],
--   subject TEXT, summary TEXT, occurred_at TEXT, created_at TEXT)

-- Contact relationships
-- contact_relationships(id INTEGER PK, contact_id_a INTEGER FK→contacts,
--   contact_id_b INTEGER FK→contacts, relationship_type TEXT, notes TEXT)
--   CHECK: contact_id_a < contact_id_b

-- Follow-ups
-- follow_ups(id INTEGER PK, contact_id INTEGER FK→contacts,
--   due_date TEXT, reason TEXT,
--   status TEXT ['pending','completed','skipped'],
--   completed_at TEXT, created_at TEXT)


-- === PROJECT TRACKER MODULE ===

-- Projects
-- projects(id INTEGER PK, name TEXT, description TEXT,
--   client_id INTEGER FK→contacts,
--   status TEXT ['idea','planning','active','paused','completed','cancelled'],
--   priority TEXT ['low','medium','high','urgent'],
--   start_date TEXT, target_date TEXT, completed_date TEXT,
--   created_at TEXT, updated_at TEXT)

-- Tasks
-- tasks(id INTEGER PK, project_id INTEGER FK→projects,
--   title TEXT, description TEXT,
--   status TEXT ['todo','in_progress','done','blocked'],
--   priority TEXT ['low','medium','high','urgent'],
--   assigned_to INTEGER FK→contacts,
--   due_date TEXT, completed_at TEXT, sort_order INTEGER,
--   created_at TEXT, updated_at TEXT)

-- Milestones
-- milestones(id INTEGER PK, project_id INTEGER FK→projects,
--   name TEXT, description TEXT, target_date TEXT, completed_date TEXT,
--   status TEXT ['pending','completed','missed'],
--   created_at TEXT)


-- === GMAIL MODULE ===

-- Emails
-- emails(id INTEGER PK, gmail_id TEXT UNIQUE, thread_id TEXT,
--   contact_id INTEGER FK→contacts, direction TEXT ['inbound','outbound'],
--   from_address TEXT, from_name TEXT, to_addresses TEXT,
--   subject TEXT, snippet TEXT, labels TEXT,
--   is_read INTEGER, is_starred INTEGER,
--   received_at TEXT, created_at TEXT,
--   account_id INTEGER FK→google_accounts)  -- NULL = pre-multi-account


-- === CALENDAR MODULE ===

-- Calendar Events
-- calendar_events(id INTEGER PK, google_event_id TEXT UNIQUE,
--   title TEXT, description TEXT, location TEXT,
--   start_time TEXT, end_time TEXT, all_day INTEGER,
--   status TEXT, attendees TEXT (JSON), contact_ids TEXT (JSON),
--   project_id INTEGER FK→projects, synced_at TEXT,
--   account_id INTEGER FK→google_accounts)  -- NULL = pre-multi-account
