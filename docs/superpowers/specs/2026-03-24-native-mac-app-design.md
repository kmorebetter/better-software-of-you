# Software of You — Native Mac App Design Spec

**Date:** 2026-03-24
**Status:** Draft
**Author:** Kerry Morrison + Claude

---

## 1. Vision

Turn Software of You from a Claude Code plugin into a native Mac desktop application. Preserve the core tenets: on-device storage, natural language as the primary interface, and Claude as the reasoning engine. Ship as a polished `.app` with a chat-first UX, contextual visual panels, and a menu bar ambient mode.

## 2. Approach

**Tauri v2 (Rust + React webview)** — Rust backend for data, sync, and API communication. React + TypeScript frontend in WKWebView for the UI. Swift ML bridge deferred to post-v1 for Apple on-device ML capabilities.

### Why Tauri

- Ships as a native `.app` (~10-15MB vs ~200MB for Electron)
- Rust backend maps nearly 1:1 to the existing MCP server (Python → Rust port of the same tool logic)
- Webview frontend lets us reuse the existing Tailwind design system
- Tauri v2 provides menu bar/tray, deep links (for OAuth), notifications, and system integration out of the box
- React gives the largest ecosystem for chat UI, markdown rendering, and component libraries

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Tauri v2 Shell                        │
│  ┌─────────────┐  ┌──────────────────────────────────┐  │
│  │  Rust Core   │  │        Webview (React + TS)      │  │
│  │             │  │  ┌────────────┬───────────────┐  │  │
│  │ • SQLite    │  │  │   Chat     │  Side Panel   │  │  │
│  │ • Claude API│◄─┤  │   Pane     │  (contextual) │  │  │
│  │ • Google    │  │  │            │               │  │  │
│  │   OAuth     │  │  │  markdown  │  dashboard    │  │  │
│  │ • Sync      │  │  │  + inline  │  entity page  │  │  │
│  │   engine    │  │  │  cards     │  calendar     │  │  │
│  │ • Tool      │  │  │            │  timeline     │  │  │
│  │   executor  │  │  └────────────┴───────────────┘  │  │
│  └──────┬──────┘  └──────────────────────────────────┘  │
│         │                                                │
│  ┌──────▼──────┐  ┌──────────────┐                      │
│  │   SQLite    │  │  Menu Bar    │                      │
│  │   (local)   │  │  Mini Mode   │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
   Claude API                    Google APIs
   (reasoning,                   (Gmail, Calendar,
    tool use)                     OAuth)
```

### Rust Core (5 responsibilities)

1. **SQLite Manager** — Owns `~/.local/share/software-of-you/soy.db`. Runs idempotent migrations on startup. Uses `rusqlite`.
2. **Tool Executor** — 18 tools exist in the current MCP server; v1 ports 11 of them to Rust Tauri commands (see Section 5). Same SQL, same logic, different language. Claude calls them via tool use; Rust executes against SQLite.
3. **Claude API Client** — Streams responses via SSE from the Messages API. Handles the tool-use loop (message → tool call → execute → return → continue). Pipes streaming tokens to the frontend for real-time "typing" feel.
4. **Google Sync Engine** — OAuth2 + PKCE via Tauri deep links (`soy://auth/callback`). Gmail + Calendar sync on a 15-minute timer. Matches emails to contacts automatically.
5. **Panel Router** — Claude's responses include structured panel hints (a `panel` field in the tool use response or a structured block in the assistant message). The Rust backend parses these hints and emits `show_panel` events to the frontend with entity type + ID. The frontend fetches panel data via a dedicated Tauri command and renders the appropriate component. This is one mechanism, not two — Claude decides what to show, Rust routes it.

### Frontend (React + TypeScript)

- **Tailwind CSS** for styling (existing design system carries over)
- **Lucide React** for icons
- **Inter** font (bundled, no CDN)
- **react-markdown + remark-gfm** for chat response rendering
- Component library for panel views (stat cards, timelines, tables, charts)

### Data Flow

```
User types message
  → Frontend sends to Rust via Tauri command
    → Rust calls Claude API (Messages endpoint) with message + tool definitions
      → Claude responds with tool calls (e.g., meeting_prep for "Sarah")
        → Rust executes tool: queries SQLite, returns structured data
          → Claude synthesizes response with narrative + panel hint
            → Frontend renders: chat shows narrative, side panel opens entity view
```

## 4. UX Design

### Interaction Model: Chat-Primary with Contextual Panel

No sidebar navigation. No tab bar. The chat IS the navigation. Users talk naturally; the app responds with text + visuals.

### State 1: Full Window (default)

Chat is full-width. Responses include **inline cards** — rich, tappable components (meeting brief, contact summary, nudge list). Cards have "Open Panel →" actions.

### State 2: Chat + Side Panel

When context demands visual detail, a panel slides out on the right (50/50 or 60/40 split). Examples:
- "Tell me about Sarah" → Sarah's entity page in panel
- "Show my dashboard" → Dashboard in panel
- "What's on my calendar?" → Week view in panel

The panel has a **Pin** button to lock it across messages. Without pin, it updates contextually or dismisses when irrelevant.

### State 3: Menu Bar (ambient mode)

Collapse to tray icon. Click → compact floating popover showing:
- Overdue items / nudges
- Next meeting
- Emails needing reply
- Quick text input for fast questions
- "Open full window" link

### Key UX Decisions

- **No traditional navigation** — chat drives everything. Can revisit if testing reveals friction.
- **Inline cards bridge chat and visuals** — quick answers stay in chat, deep dives open the panel.
- **First launch = onboarding conversation** — same flow (name → role → focus → style) rendered as a beautiful in-chat experience.
- **Component composition for "show me X"** — Claude returns a JSON layout spec, frontend renders from component library. No raw HTML generation. Cheap in tokens, consistent in design.

### Component Composition System

Instead of Claude generating HTML, it returns structured composition instructions:

```json
{
  "layout": "two-column",
  "components": [
    {"type": "timeline", "query": "interactions WHERE contact_id = 5", "range": "6 months"},
    {"type": "stat-grid", "metrics": ["emails_sent", "days_silent", "meetings"]}
  ]
}
```

The app renders from its pre-built component library. If a request can't be expressed with existing components, that's a signal to build a new component — not to have Claude freestyle.

## 5. v1 Modules (Core)

Four modules ship built-in:

| Module | What it provides |
|--------|-----------------|
| **CRM** | Contacts, interactions, follow-ups, relationship scores, entity pages |
| **Gmail** | Email sync, search, compose, contact matching |
| **Calendar** | Event sync, meeting prep, week view |
| **Conversation Intelligence** | Transcript analysis, commitment extraction, coaching insights |
| **Inbox** | Quick capture queue, routing to contacts/projects/decisions/journal |

Plus **User Profile** (onboarding, preferences) and **System** (status, health) as built-in infrastructure.

### Tools (v1)

Ported from the existing MCP server:

| Tool | v1 | Description |
|------|:---:|------------|
| `tool_contacts` | ✓ | Add/edit/list/find contacts |
| `tool_interactions` | ✓ | Log calls/emails/meetings, manage follow-ups |
| `tool_email` | ✓ | Compose/send, search inbox |
| `tool_calendar` | ✓ | List events, create entries, find free time |
| `tool_transcripts` | ✓ | Import, extract commitments, insights |
| `tool_intelligence` | ✓ | Meeting prep, nudges, commitments, relationship pulse, weekly review |
| `tool_search` | ✓ | FTS5 search across all modules |
| `tool_overview` | ✓ | Dashboard data aggregation |
| `tool_inbox` | ✓ | Quick capture and routing |
| `tool_profile` | ✓ | User identity and preferences |
| `tool_system` | ✓ | Status, module list, connection status |
| `tool_projects` | — | v2 add-on module |
| `tool_journal` | — | v2 add-on module |
| `tool_notes` | — | v2 add-on module |
| `tool_decisions` | — | v2 add-on module |
| `tool_slack` | — | v2 add-on module |
| `tool_views` | — | Replaced by component composition system |
| `tool_semantic_search` | — | Post-v1, with Swift ML bridge |

**Note:** The current MCP server has 18 tool files total. The v1 tool set covers the 4 core modules plus infrastructure. Deferred tools map to deferred modules.

### Computed Views

All existing computed views (`v_contact_health`, `v_commitment_status`, `v_nudge_items`, `v_nudge_summary`, `v_discovery_candidates`, `v_meeting_prep`, `v_project_health`, `v_email_response_queue`) port directly. They keep tool implementations thin — tools query views, Claude narrates results.

## 6. Module Architecture (Extensibility)

v1 modules are built-in, but the architecture supports add-on modules from day one.

### Module Structure

```
~/.local/share/software-of-you/modules/
├── projects/
│   ├── manifest.json       # Tables, tools, UI components, enhancements
│   ├── migrations/         # SQL migrations for this module
│   └── components/         # React components for panel views
└── notes/
    ├── manifest.json
    └── ...
```

### manifest.json

Each module declares:
- **migrations** — SQL files for tables it needs
- **tools** — Tool definitions added to Claude's context when active
- **components** — React components registered for the side panel
- **enhancements** — Cross-module features (e.g., "when CRM is also installed, show project history on contact pages")

### Install Flow (v2)

1. App fetches module registry (hosted JSON)
2. User selects a module → payment (StoreKit or Stripe depending on distribution channel)
3. App downloads module bundle → runs migrations → registers tools → loads components
4. Hot-reload, no restart needed

## 7. Distribution & Business Model

### Dual Distribution

| Channel | App | Modules | Cut |
|---------|-----|---------|-----|
| **App Store** | Free download | In-app purchase via StoreKit | Apple takes 15% (Small Business Program) |
| **Direct** (website DMG) | Free download | Stripe / Lemon Squeezy checkout | ~3% payment processing |

The app detects its distribution channel at runtime (App Store receipt exists → StoreKit path; no receipt → Stripe path). One codebase, two payment integrations.

### AI Costs

- **BYOK (Bring Your Own Key)** — User provides their Claude API key. No AI cost to us. Power user / developer audience.
- **Bundled** — We provide Claude API access, cost baked into module pricing or a subscription tier. Consumer audience.

### Pricing (TBD)

- Core app: Free (4 modules included)
- Add-on modules: One-time purchase ($X each) or subscription
- API access tiers: BYOK (free) vs. bundled (subscription)

Specific pricing to be determined based on API cost modeling and market positioning.

## 8. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Shell | Tauri v2 | Native `.app`, menu bar, deep links, small binary |
| Backend | Rust | Tauri native, excellent SQLite + HTTP support |
| Frontend | React + TypeScript | Largest ecosystem for chat UIs + components |
| Styling | Tailwind CSS | Existing design system carries over |
| Database | SQLite via `rusqlite` | Direct schema port, on-device storage |
| AI | Claude API (Messages + tool use) | Full reasoning capability |
| Auth | Google OAuth2 + PKCE | Desktop flow via Tauri deep links |
| Icons | Lucide React | Already the icon set |
| Fonts | Inter (bundled) | No CDN dependency |
| Markdown | react-markdown + remark-gfm | Chat response rendering |
| Streaming | SSE via reqwest | Claude API streaming |

## 9. Claude Integration: System Prompt & Context

### System Prompt Construction

The Rust backend assembles Claude's system prompt dynamically on each API call. This replaces the static CLAUDE.md that the CLI plugin uses.

**System prompt structure:**

```
[1] Core identity and behavior rules
    - "You are Software of You, a personal data platform..."
    - Data integrity rules (never fabricate, NULL over fiction)
    - Response style (concise, conversational, cross-reference everything)

[2] User profile context
    - Name, role, communication style preference
    - Loaded from user_profile table at session start

[3] Active module context
    - Which modules are installed → determines which tools are available
    - Cross-module enhancement rules (e.g., "CRM + Calendar: show client context in meeting prep")

[4] Tool definitions
    - JSON schemas for each active tool (same format as MCP tool definitions)
    - Only tools for active modules are included

[5] Panel instruction format
    - Tell Claude how to emit panel hints in its responses
    - "When referencing an entity, include a structured panel block with type and ID"

[6] Component composition schema
    - Available component types for "show me X" requests
    - JSON format for layout composition responses
```

Sections [1] and [5-6] are static. Sections [2-4] are assembled from the database at session start and cached until a module is added/removed or user profile changes.

### Context Window Management

- **Conversation history** is maintained in-memory during a session.
- When approaching the context limit (~180K tokens for Sonnet), the app **summarizes older messages** — the Rust backend calls Claude with the older portion of the conversation and a "summarize this conversation so far" prompt, then replaces the detailed history with the summary. The user sees the full history in the chat UI (it's stored locally); Claude sees the summary + recent messages.
- **Tool results are not stored in conversation history verbatim.** The Rust backend keeps the tool call and a compact summary of the result. Full tool outputs are available for the current turn only.

## 10. Conversation Persistence

### Chat History Storage

Conversations are stored in SQLite in a `conversations` table:

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    title TEXT,           -- Auto-generated or user-set
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role TEXT,            -- 'user', 'assistant'
    content TEXT,         -- Markdown text
    panel_hint TEXT,      -- JSON: entity type + ID for panel, if any
    tool_calls TEXT,      -- JSON: tool calls made during this turn
    created_at TEXT
);
```

- **New conversation** starts each time the app launches or user explicitly starts one.
- **Conversation list** accessible via "Show my conversations" or a subtle history icon.
- **Search past conversations** via FTS5 on message content.
- Conversations are local-only — never sent to any server.

## 11. Security & Credential Storage

- **Claude API key** (BYOK mode) — stored in macOS Keychain via Tauri's `tauri-plugin-keychain` or direct Security framework calls.
- **Google OAuth tokens** — stored in Keychain, not on disk. Refresh tokens are encrypted at rest.
- **Database** — not encrypted in v1 (it's local, user-owned data). Encryption (SQLCipher) is a post-v1 option if needed.
- **No telemetry** — the app sends nothing home. API calls go to Anthropic and Google only.
- **App Store sandboxing** — the App Store version runs in Apple's sandbox. Direct version does not, but follows the same security practices.

### Settings Access

Settings is accessed via chat ("open settings" or Cmd+,) and renders as a panel view. Contains:
- Claude API key management (BYOK)
- Google account connection/disconnection
- User profile editing (name, role, communication style)
- Installed modules list
- Data location and backup controls
- About / version info

## 12. Error Handling (v1)

| Scenario | Behavior |
|----------|----------|
| No internet | Chat shows "I need an internet connection for conversations. You can still browse your data." Local data browsing works via pre-built panel views. |
| Claude API down | Retry with exponential backoff (3 attempts). Then: "Claude is temporarily unavailable. Your data is safe — try again in a moment." |
| Claude API key invalid | BYOK: prompt user to check their key in settings. Bundled: transparent retry / fallback messaging. |
| Google OAuth expired | Silent token refresh. If refresh fails, show non-blocking banner: "Google sync paused — reconnect in settings." |
| Google sync fails | Use cached data. No error shown unless user explicitly requests fresh data. |
| Tool execution error | Claude sees the error in the tool result and can explain it to the user or retry with a different approach. |
| Database corruption | Detected on startup. Offer to restore from most recent backup (auto-backup on each migration). |

## 13. v1 Component Catalog

The frontend must implement these component types for the panel and composition system:

| Component | Used in | Description |
|-----------|---------|-------------|
| `stat-card` | Dashboard, entity page | Single metric with label, value, trend indicator |
| `stat-grid` | Dashboard, entity page | Grid of 3-4 stat cards |
| `contact-card` | Entity page, search results | Avatar, name, role, company, health indicator |
| `contact-list` | Contacts panel | Scrollable list of contact cards |
| `timeline` | Entity page, conversations | Chronological event list (emails, meetings, calls) |
| `email-list` | Email panel, entity page | Email subjects with date, sender, read status |
| `calendar-week` | Calendar panel | Week grid with events |
| `calendar-event` | Meeting prep | Single event with time, attendees, location |
| `commitment-list` | Nudges, entity page | Commitments with status, owner, due date, urgency |
| `nudge-feed` | Dashboard, menu bar | Prioritized list of nudge items by urgency tier |
| `meeting-prep` | Pre-meeting panel | Attendee briefs, open threads, suggested opener |
| `transcript-summary` | Conversation intelligence | Talk metrics, key topics, commitments extracted |
| `markdown-card` | Chat inline | Rich markdown content in a card wrapper |
| `empty-state` | Any panel | Friendly message when no data exists for a view |

Additional component types can be added as modules ship. The composition system is extensible — Claude can only reference components that exist in the frontend registry.

## 14. Known Challenges

| Challenge | Mitigation |
|-----------|-----------|
| Google OAuth in desktop app | Tauri deep links + custom URI scheme (`soy://auth/callback`) |
| Streaming Claude API → webview | SSE via `reqwest`, pipe chunks to frontend via Tauri events |
| Chat + panel feeling cohesive | Inline cards as bridge; panel is additive, not mandatory |
| WKWebView CSS differences | Minor; Tailwind handles most cross-browser issues |
| Rust ↔ Swift bridging (future ML) | Deferred to post-v1; Claude API covers all reasoning |
| App Store review | No private API usage; standard webview app pattern |

## 15. Future (Post-v1)

- **Swift ML bridge** — On-device embeddings, NER, classification via Core ML / Apple Foundation Models
- **Module marketplace** — Registry, purchasing, hot-install
- **Offline mode** — Degraded but functional (browse, search, add data) when no internet
- **Multi-device sync** — CloudKit or custom sync for multiple Macs (way later)
- **iOS companion** — Tauri doesn't support iOS, but a lightweight Swift app reading the same SQLite could work via iCloud

## 16. Open Questions

1. App name — "Software of You" or something shorter for the native app?
2. Claude model selection — Sonnet (cheaper, faster) vs. Opus (more capable) as default? User-selectable?
3. Onboarding: do we show a product tour alongside the chat onboarding, or is the chat enough?
4. Should the menu bar mode run a periodic nudge check (e.g., every hour) and show a native notification?
5. Module pricing specifics — one-time vs. subscription, price points
