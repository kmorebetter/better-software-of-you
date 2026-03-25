# Next Session: Make the Native App as Smart as the Original SoY

## Context

The native Tauri app works — chat, tool use, Google sync, side panels. But the in-app Claude feels significantly dumber than the original SoY Claude Code plugin. Tonight's session fixed the most critical issues (conversation memory, broken SQL queries, rigid email sync), but there's a deeper architectural gap.

The original SoY plugin was smart because Claude Code gave it:
- Full CLAUDE.md with schema docs, module awareness, computed view definitions
- Native context window management (summarization, trimming)
- Direct SQLite access (Claude wrote queries on the fly, seeing schema)
- Proactive data freshness (auto-sync before answering)

The native app routes everything through pre-built tools, which is right for a shipped product — but the system prompt doesn't give Claude enough knowledge to use those tools intelligently.

## What to Build Tomorrow

### 1. Context Management (most impactful)

**Problem:** Every tool result is saved verbatim to conversation history. After 10 tool calls, Claude receives 50KB+ of stale JSON, crowding out recent context and confusing it.

**Fix:** Before sending history to Claude, compress old tool results:
- Last 3 tool interactions: send full results
- Older tool interactions: replace content with a 1-2 line summary (e.g., "Used get_profile for Alex Somerville — returned contact details, 12 emails, 0 commitments")
- Very old messages (>20 turns back): trim to role + first 100 chars
- Add a token budget check: if history exceeds ~80K tokens, aggressively summarize

**Where:** `commands.rs` `send_message()` — after loading history, before building the messages array. Add a `compress_history()` function.

### 2. Dynamic System Prompt (makes Claude feel smart from turn 1)

**Problem:** The system prompt is static. Claude has to make tool calls just to know basic things like "how many contacts do I have" or "what's on the calendar today." The original SoY injected this data into CLAUDE.md.

**Fix:** Inject a "Current State" block into the system prompt with:
- Today's date + day of week
- Contact count + top 3 most recent contacts (name, company)
- Today's calendar events (time, title, attendees)
- Unread email count
- Last sync timestamps
- Any pending nudges/commitments count

**Where:** `claude.rs` `build_system_prompt()` — already has some of this (contact_count, google status). Expand it with live queries. Keep it under 500 tokens total.

### 3. Schema Awareness for Claude

**Problem:** The original SoY let Claude write SQL directly against a documented schema. The native app's tools are pre-built, which is better for reliability, but Claude doesn't know what data shapes the tools return. It guesses, sometimes wrong.

**Fix:** Add a "Tool Output Reference" section to the system prompt:
```
## Tool Output Shapes
- contacts(action: "search"): returns {contact, tags, interactions, follow_ups, recent_emails, health}
- get_profile(contact_id): returns {contact, tags, notes, interactions, follow_ups, emails, calendar_events, transcripts, commitments, health}
  - health: {email_count, interaction_count, days_silent, relationship_depth, trajectory}
- get_overview(): returns {contacts: {total, recent}, follow_ups, calendar, emails: {unread_count}, commitments, nudges, recent_activity}
```

This lets Claude reference tool results accurately in conversation without re-calling tools.

### 4. Prompt Cleanup (tighter = better adherence)

**Problem:** ~30% of the system prompt is negative instructions ("don't reference menus", "don't say sync takes 15 minutes", "don't expose SQL"). These waste tokens and create a "no" energy that makes Claude hedgy.

**Fix:** Rewrite to affirmative voice only:
- "You are a chat interface with a side panel" (not "there are NO menus, NO navigation...")
- "Sync takes ~30 seconds" (not "Never say sync takes more than a minute")
- Cut the duplicated onboarding instructions (they repeat what CLAUDE.md already says)

Target: cut system prompt from ~3KB to ~2KB while adding the dynamic context from #2.

### 5. Reconnect Google (user action needed)

After tonight's session, the Google OAuth now requests `documents.readonly` scope for transcript import. The user needs to:
1. Open Settings (Cmd+,)
2. Disconnect Google
3. Reconnect — the new consent screen will include Docs access

Remind them at session start.

## Files to Touch

| File | What to change |
|------|---------------|
| `src-tauri/src/claude.rs` | `build_system_prompt()` — dynamic context injection, prompt rewrite, tool output shapes |
| `src-tauri/src/commands.rs` | `send_message()` — add `compress_history()` before API call |
| `src-tauri/src/claude.rs` | New `compress_history()` function |

## What's Already Working

- Chat with tool use loop (max 10 rounds)
- Conversation persistence with full tool context
- Google OAuth + Gmail/Calendar sync (with flexible email count)
- Google Meet transcript import pipeline
- Side panel system with dashboard, contact, calendar, email, nudges, commitments panels
- macOS native menus (Quit, Copy, Paste all work)
- API key persisted in SQLite (survives rebuilds)
- Tool indicator pills in chat UI
- Markdown rendering with typography plugin

## Build & Run

```bash
cd soy-app
source ~/.cargo/env
npx tauri build
open src-tauri/target/release/bundle/macos/Software\ of\ You.app
```

## Known Issues Not Yet Fixed

- Auto-scroll jitter during streaming (scroll fights with new content)
- No React Error Boundary (unhandled errors crash the panel)
- LoadingScreen has low contrast text
- InlineCard component exists but isn't integrated anywhere
- The `contacts` tool `search` action pattern-matches `contact_name` but the tool definition says `name` — check for mismatch
