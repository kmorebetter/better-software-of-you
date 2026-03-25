# Software of You — Native Mac App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native Mac desktop app (Tauri v2) for Software of You with chat-first UX, contextual side panel, and menu bar mode.

**Architecture:** Rust backend (SQLite + Claude API + Google sync) with React + TypeScript frontend in a Tauri webview. Chat-primary interface where Claude reasons via tool use against local SQLite data. Side panel slides out for entity pages, dashboards, and composed views.

**Tech Stack:** Tauri v2, Rust, React 18, TypeScript, Tailwind CSS, rusqlite, reqwest, react-markdown, Lucide React, Inter font

**Spec:** `docs/superpowers/specs/2026-03-24-native-mac-app-design.md`

---

## File Structure

```
soy-app/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   ├── icons/                        # App icons (Tauri generates from a single 1024x1024)
│   ├── migrations/                   # SQL migration files (ported from data/migrations/)
│   │   ├── 001_core_schema.sql       # ← from data/migrations/001_core_schema.sql
│   │   ├── 002_crm_module.sql        # ← from 002_crm_module.sql
│   │   ├── 003_project_tracker.sql   # ← from 003_project_tracker.sql (tables exist for schema compat)
│   │   ├── 004_gmail_module.sql      # ← from 004_gmail_module.sql
│   │   ├── 005_calendar_module.sql   # ← from 005_calendar_module.sql
│   │   ├── 006_conversation_intel.sql # ← from 006_conversation_intelligence.sql
│   │   ├── 007_call_intelligence.sql # ← from 007_call_intelligence.sql
│   │   ├── 008_transcript_sources.sql # ← from 008_transcript_sources.sql
│   │   ├── 009_decision_outcomes.sql # ← from 009_decision_outcomes.sql
│   │   ├── 010_performance_indexes.sql # ← from 010_performance_indexes.sql
│   │   ├── 011_standalone_notes.sql  # ← from 011_standalone_notes.sql
│   │   ├── 012_google_multi_account.sql # ← from 012_google_multi_account.sql
│   │   ├── 013_user_profiles.sql     # ← from 013_user_profiles.sql
│   │   ├── 014_computed_views.sql    # ← from 014_computed_views.sql
│   │   ├── 015_google_multi_account_v2.sql # ← from 015_google_multi_account_v2.sql
│   │   ├── 016_google_contacts_link.sql # ← from 016_google_contacts_link.sql
│   │   ├── 017_slack_integration.sql # ← from 017_slack_integration.sql (stub, tables only)
│   │   ├── 018_slack_auth.sql        # ← from 018_slack_auth.sql (stub)
│   │   ├── 019_email_opportunities.sql # ← from 019_email_opportunities.sql
│   │   ├── 020_inbox_module.sql      # ← from 020_inbox_module.sql
│   │   ├── 021_proactive.sql         # ← from 021_proactive_system.sql
│   │   ├── 022_fts5_search.sql       # ← from 022_fts5_search.sql
│   │   ├── 023_embeddings.sql        # ← from 023_embeddings_meta.sql
│   │   ├── 024_monitored_inboxes.sql # ← from 024_monitored_inboxes.sql
│   │   └── 025_conversations.sql     # NEW: chat history tables for native app
│   └── src/
│       ├── main.rs                   # Tauri entry point, window creation
│       ├── lib.rs                    # Module declarations, Tauri command registration
│       ├── state.rs                  # AppState: DB pool, settings, Claude client
│       ├── db.rs                     # Database manager: connection, migrations, query helpers
│       ├── claude.rs                 # Claude API client: streaming, tool loop, system prompt
│       ├── tools/
│       │   ├── mod.rs                # Tool registry: schema definitions, dispatch
│       │   ├── contacts.rs           # Contact CRUD + cross-references
│       │   ├── interactions.rs       # Interaction logging + follow-ups
│       │   ├── email.rs              # Email search + browse
│       │   ├── calendar.rs           # Calendar events + free time
│       │   ├── transcripts.rs        # Transcript import + analysis storage
│       │   ├── intelligence.rs       # Meeting prep, nudges, commitments, pulse, weekly review
│       │   ├── search.rs             # FTS5 + keyword fallback
│       │   ├── overview.rs           # Dashboard data aggregation
│       │   ├── inbox.rs              # Quick capture + routing
│       │   ├── profile.rs            # User profile + rich contact profile
│       │   └── system.rs             # Status, health, Google connection check
│       ├── google/
│       │   ├── mod.rs                # Google module exports
│       │   ├── oauth.rs              # OAuth2 + PKCE, deep link handler
│       │   ├── gmail.rs              # Gmail API: fetch messages, match contacts
│       │   └── calendar.rs           # Calendar API: fetch events, link contacts
│       └── commands.rs               # Tauri commands: send_message, get_panel_data, etc.
├── src/
│   ├── index.html                    # HTML entry point
│   ├── main.tsx                      # React entry, Tauri event listeners
│   ├── App.tsx                       # Main layout: chat + panel + transitions
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatPane.tsx          # Chat container with message list + input
│   │   │   ├── MessageList.tsx       # Scrollable message history
│   │   │   ├── MessageBubble.tsx     # Single message: markdown + inline cards
│   │   │   ├── ChatInput.tsx         # Text input with send button
│   │   │   ├── InlineCard.tsx        # Rich tappable card in chat responses
│   │   │   └── StreamingText.tsx     # Streaming response with cursor
│   │   ├── panel/
│   │   │   ├── SidePanel.tsx         # Panel container with slide animation
│   │   │   ├── PanelRouter.tsx       # Routes panel type → component
│   │   │   ├── Dashboard.tsx         # Dashboard view
│   │   │   ├── EntityPage.tsx        # Contact detail page
│   │   │   ├── CalendarWeek.tsx      # Week view
│   │   │   ├── EmailList.tsx         # Email list view
│   │   │   ├── Timeline.tsx          # Chronological event list
│   │   │   ├── StatGrid.tsx          # Grid of stat cards
│   │   │   ├── StatCard.tsx          # Single metric card
│   │   │   ├── CommitmentList.tsx    # Commitments with status + urgency
│   │   │   ├── NudgeFeed.tsx         # Nudge items by urgency tier
│   │   │   ├── MeetingPrep.tsx       # Meeting prep brief
│   │   │   ├── ContactList.tsx       # Scrollable contact list
│   │   │   ├── ContactCard.tsx       # Contact summary card
│   │   │   ├── TranscriptSummary.tsx # Transcript analysis view
│   │   │   ├── Settings.tsx          # Settings panel
│   │   │   └── EmptyState.tsx        # Friendly empty state
│   │   ├── menubar/
│   │   │   └── MenuBarWindow.tsx     # Compact menu bar popover
│   │   └── shared/
│   │       ├── Avatar.tsx            # Contact avatar (initials)
│   │       ├── Badge.tsx             # Status/urgency badge
│   │       ├── Card.tsx              # Base card wrapper
│   │       └── Spinner.tsx           # Loading indicator
│   ├── hooks/
│   │   ├── useChat.ts               # Chat state: messages, streaming, send
│   │   ├── usePanel.ts              # Panel state: type, data, pin, open/close
│   │   └── useStream.ts             # Tauri event listener for streaming tokens
│   ├── lib/
│   │   ├── commands.ts              # Typed Tauri invoke() wrappers
│   │   └── types.ts                 # Shared TypeScript types
│   └── styles/
│       └── globals.css              # Tailwind directives, Inter font, custom styles
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── vite.config.ts
```

---

## Phase 1: Shell + Chat (Get something on screen)

**Goal:** A Tauri window where you can talk to Claude and get streamed responses. No tools, no database, no panel — just chat.

### Task 1: Scaffold Tauri v2 + React project

**Files:**
- Create: `soy-app/` (entire scaffold)

- [ ] **Step 1: Create the Tauri v2 project**

```bash
cd /Users/kerrymorrison/Projects/PersonalProjects/better-software-of-you
npm create tauri-app@latest soy-app -- --template react-ts --manager npm
```

Select: TypeScript, React, npm

- [ ] **Step 2: Install frontend dependencies**

```bash
cd soy-app
npm install react-markdown remark-gfm lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Configure Tailwind**

Replace `src/styles/globals.css` (or `src/styles.css` depending on scaffold):

```css
@import "tailwindcss";

@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter-Variable.woff2') format('woff2');
  font-weight: 100 900;
  font-display: swap;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  @apply bg-white text-zinc-900 antialiased;
}
```

Download Inter variable font to `soy-app/public/fonts/Inter-Variable.woff2`:
```bash
mkdir -p public/fonts
curl -L -o public/fonts/Inter-Variable.woff2 "https://github.com/rsms/inter/raw/master/docs/font-files/InterVariable.woff2"
```

- [ ] **Step 4: Update vite.config.ts for Tailwind v4**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: "ws", host, port: 1421 } : undefined,
    watch: { ignored: ["**/src-tauri/**"] },
  },
}));
```

- [ ] **Step 5: Configure Tauri window**

Update `src-tauri/tauri.conf.json` — set window title, size, and app identifier:

```json
{
  "app": {
    "windows": [
      {
        "title": "Software of You",
        "width": 1200,
        "height": 800,
        "minWidth": 800,
        "minHeight": 600,
        "center": true
      }
    ]
  },
  "identifier": "com.softwareofyou.app"
}
```

- [ ] **Step 6: Add Rust dependencies to Cargo.toml**

Add to `src-tauri/Cargo.toml` under `[dependencies]`:

```toml
serde = { version = "1", features = ["derive"] }
serde_json = "1"
rusqlite = { version = "0.31", features = ["bundled"] }
reqwest = { version = "0.12", features = ["stream", "json"] }
tokio = { version = "1", features = ["full"] }
dirs = "5"
futures-util = "0.3"
keyring = "3"
chrono = { version = "0.4", features = ["serde"] }
uuid = { version = "1", features = ["v4"] }
```

- [ ] **Step 7: Verify the scaffold runs**

```bash
cd soy-app
npm run tauri dev
```

Expected: A Tauri window opens with the default React welcome page.

- [ ] **Step 8: Commit**

```bash
git add soy-app/
git commit -m "feat: scaffold Tauri v2 + React + Tailwind project for native SoY app"
```

---

### Task 2: Build the chat UI

**Files:**
- Create: `src/components/chat/ChatPane.tsx`
- Create: `src/components/chat/MessageList.tsx`
- Create: `src/components/chat/MessageBubble.tsx`
- Create: `src/components/chat/ChatInput.tsx`
- Create: `src/components/chat/StreamingText.tsx`
- Create: `src/components/shared/Spinner.tsx`
- Create: `src/hooks/useChat.ts`
- Create: `src/lib/types.ts`
- Create: `src/lib/commands.ts`
- Modify: `src/App.tsx`
- Modify: `src/main.tsx`

- [ ] **Step 1: Define shared types**

Create `src/lib/types.ts`:

```typescript
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  panelHint?: PanelHint;
  timestamp: string;
  isStreaming?: boolean;
}

export interface PanelHint {
  type: "contact" | "dashboard" | "calendar" | "email" | "timeline" | "meeting-prep" | "nudges" | "commitments" | "settings" | "composition";
  entityId?: number;
  title?: string;
  composition?: CompositionSpec;
}

export interface CompositionSpec {
  layout: "single" | "two-column" | "stacked";
  components: ComponentSpec[];
}

export interface ComponentSpec {
  type: string;
  props: Record<string, unknown>;
}

export interface StreamEvent {
  token?: string;
  done?: boolean;
  panelHint?: PanelHint;
  error?: string;
}
```

- [ ] **Step 2: Create Tauri command wrappers**

Create `src/lib/commands.ts`:

```typescript
import { invoke } from "@tauri-apps/api/core";

export async function sendMessage(message: string, conversationId?: string): Promise<string> {
  return invoke("send_message", { message, conversationId });
}

export async function getApiKeyStatus(): Promise<{ hasKey: boolean }> {
  return invoke("get_api_key_status");
}

export async function setApiKey(key: string): Promise<void> {
  return invoke("set_api_key", { key });
}
```

- [ ] **Step 3: Create useChat hook**

Create `src/hooks/useChat.ts`:

```typescript
import { useState, useCallback, useRef } from "react";
import { listen } from "@tauri-apps/api/event";
import { Message, StreamEvent, PanelHint } from "../lib/types";
import { sendMessage } from "../lib/commands";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamBuffer = useRef("");
  const [pendingPanelHint, setPendingPanelHint] = useState<PanelHint | null>(null);

  const send = useCallback(async (content: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    streamBuffer.current = "";

    const unlisten = await listen<StreamEvent>("chat-stream", (event) => {
      const data = event.payload;

      if (data.token) {
        streamBuffer.current += data.token;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, content: streamBuffer.current };
          }
          return updated;
        });
      }

      if (data.panelHint) {
        setPendingPanelHint(data.panelHint);
      }

      if (data.done) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, isStreaming: false };
          }
          return updated;
        });
        setIsStreaming(false);
        unlisten();
      }

      if (data.error) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: `Something went wrong: ${data.error}`,
              isStreaming: false,
            };
          }
          return updated;
        });
        setIsStreaming(false);
        unlisten();
      }
    });

    try {
      await sendMessage(content);
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          updated[updated.length - 1] = {
            ...last,
            content: `Failed to send message: ${err}`,
            isStreaming: false,
          };
        }
        return updated;
      });
      setIsStreaming(false);
      unlisten();
    }
  }, []);

  return { messages, isStreaming, send, pendingPanelHint, setPendingPanelHint };
}
```

- [ ] **Step 4: Create chat components**

Create `src/components/shared/Spinner.tsx`:

```tsx
export function Spinner() {
  return (
    <div className="flex items-center gap-1.5 py-2">
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.3s]" />
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.15s]" />
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" />
    </div>
  );
}
```

Create `src/components/chat/StreamingText.tsx`:

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface StreamingTextProps {
  content: string;
  isStreaming: boolean;
}

export function StreamingText({ content, isStreaming }: StreamingTextProps) {
  return (
    <div className="prose prose-zinc prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-zinc-400 animate-pulse ml-0.5 align-text-bottom" />
      )}
    </div>
  );
}
```

Create `src/components/chat/MessageBubble.tsx`:

```tsx
import { Message } from "../../lib/types";
import { StreamingText } from "./StreamingText";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-900 text-white"
            : "bg-zinc-100 text-zinc-900"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <StreamingText
            content={message.content}
            isStreaming={message.isStreaming ?? false}
          />
        )}
      </div>
    </div>
  );
}
```

Create `src/components/chat/MessageList.tsx`:

```tsx
import { useEffect, useRef } from "react";
import { Message } from "../../lib/types";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-zinc-400">
          <p className="text-lg font-medium mb-1">Software of You</p>
          <p className="text-sm">Your personal data platform. Say hello.</p>
        </div>
      )}
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
```

Create `src/components/chat/ChatInput.tsx`:

```tsx
import { useState, useRef, useCallback } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  };

  return (
    <div className="border-t border-zinc-200 px-6 py-4">
      <div className="flex items-end gap-3 bg-zinc-100 rounded-2xl px-4 py-3">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Talk to SoY..."
          disabled={disabled}
          rows={1}
          className="flex-1 bg-transparent text-sm text-zinc-900 placeholder-zinc-400 resize-none outline-none"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="p-1.5 rounded-full bg-zinc-900 text-white disabled:opacity-30 hover:bg-zinc-700 transition-colors"
        >
          <SendHorizontal size={16} />
        </button>
      </div>
    </div>
  );
}
```

Create `src/components/chat/ChatPane.tsx`:

```tsx
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { Message } from "../../lib/types";

interface ChatPaneProps {
  messages: Message[];
  isStreaming: boolean;
  onSend: (message: string) => void;
}

export function ChatPane({ messages, isStreaming, onSend }: ChatPaneProps) {
  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} />
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
```

- [ ] **Step 5: Wire up App.tsx**

Replace `src/App.tsx`:

```tsx
import { ChatPane } from "./components/chat/ChatPane";
import { useChat } from "./hooks/useChat";

function App() {
  const { messages, isStreaming, send } = useChat();

  return (
    <div className="h-screen flex">
      <div className="flex-1 flex flex-col">
        <ChatPane messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
    </div>
  );
}

export default App;
```

Update `src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 6: Commit**

```bash
git add soy-app/src/
git commit -m "feat: build chat UI with message list, input, and streaming text"
```

---

### Task 3: Claude API streaming in Rust

**Files:**
- Create: `src-tauri/src/claude.rs`
- Create: `src-tauri/src/state.rs`
- Create: `src-tauri/src/commands.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/main.rs`

- [ ] **Step 1: Create AppState**

Create `src-tauri/src/state.rs`:

```rust
use std::sync::Mutex;

pub struct AppState {
    pub api_key: Mutex<Option<String>>,
}

impl AppState {
    pub fn new() -> Self {
        // Try loading from keychain on startup
        let key = keyring::Entry::new("com.softwareofyou.app", "claude-api-key")
            .ok()
            .and_then(|e| e.get_password().ok());

        Self {
            api_key: Mutex::new(key),
        }
    }
}
```

- [ ] **Step 2: Create Claude API client**

Create `src-tauri/src/claude.rs`:

```rust
use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter};

const CLAUDE_API_URL: &str = "https://api.anthropic.com/v1/messages";
const MODEL: &str = "claude-sonnet-4-20250514";

#[derive(Serialize, Clone)]
pub struct StreamEvent {
    pub token: Option<String>,
    pub done: Option<bool>,
    pub panel_hint: Option<Value>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct MessageRequest {
    model: String,
    max_tokens: u32,
    system: String,
    messages: Vec<ChatMessage>,
    stream: bool,
}

#[derive(Serialize, Deserialize, Clone)]
struct ChatMessage {
    role: String,
    content: String,
}

pub async fn stream_message(
    app: &AppHandle,
    api_key: &str,
    user_message: &str,
) -> Result<(), String> {
    let client = Client::new();

    let system_prompt = build_system_prompt();

    let request = MessageRequest {
        model: MODEL.to_string(),
        max_tokens: 4096,
        system: system_prompt,
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: user_message.to_string(),
        }],
        stream: true,
    };

    let response = client
        .post(CLAUDE_API_URL)
        .header("x-api-key", api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type", "application/json")
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("API request failed: {}", e))?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("API error {}: {}", status, body));
    }

    let mut stream = response.bytes_stream();
    let mut buffer = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| format!("Stream error: {}", e))?;
        buffer.push_str(&String::from_utf8_lossy(&chunk));

        // Process complete SSE events from buffer
        while let Some(pos) = buffer.find("\n\n") {
            let event_text = buffer[..pos].to_string();
            buffer = buffer[pos + 2..].to_string();

            for line in event_text.lines() {
                if let Some(data) = line.strip_prefix("data: ") {
                    if data == "[DONE]" {
                        continue;
                    }
                    if let Ok(event) = serde_json::from_str::<Value>(data) {
                        match event["type"].as_str() {
                            Some("content_block_delta") => {
                                if let Some(text) = event["delta"]["text"].as_str() {
                                    let _ = app.emit("chat-stream", StreamEvent {
                                        token: Some(text.to_string()),
                                        done: None,
                                        panel_hint: None,
                                        error: None,
                                    });
                                }
                            }
                            Some("message_stop") => {
                                let _ = app.emit("chat-stream", StreamEvent {
                                    token: None,
                                    done: Some(true),
                                    panel_hint: None,
                                    error: None,
                                });
                            }
                            Some("error") => {
                                let msg = event["error"]["message"]
                                    .as_str()
                                    .unwrap_or("Unknown error");
                                let _ = app.emit("chat-stream", StreamEvent {
                                    token: None,
                                    done: None,
                                    panel_hint: None,
                                    error: Some(msg.to_string()),
                                });
                            }
                            _ => {}
                        }
                    }
                }
            }
        }
    }

    Ok(())
}

fn build_system_prompt() -> String {
    // Phase 1: minimal system prompt. Will expand in Phase 2 with tools.
    r#"You are Software of You — a personal data platform running as a native Mac app.
You help users manage their relationships, track conversations, and stay on top of commitments.
Be concise and direct. Use markdown for formatting. No filler.
When you don't have data to answer a question, say so honestly."#.to_string()
}
```

- [ ] **Step 3: Create Tauri commands**

Create `src-tauri/src/commands.rs`:

```rust
use crate::claude;
use crate::state::AppState;
use tauri::{AppHandle, State};

#[tauri::command]
pub async fn send_message(
    app: AppHandle,
    state: State<'_, AppState>,
    message: String,
) -> Result<String, String> {
    let api_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .clone()
        .ok_or_else(|| "No API key set. Please set your Claude API key first.".to_string())?;

    claude::stream_message(&app, &api_key, &message).await?;
    Ok("done".to_string())
}

#[tauri::command]
pub async fn get_api_key_status(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let has_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .is_some();
    Ok(serde_json::json!({ "hasKey": has_key }))
}

#[tauri::command]
pub async fn set_api_key(state: State<'_, AppState>, key: String) -> Result<(), String> {
    // Store in keychain
    let entry = keyring::Entry::new("com.softwareofyou.app", "claude-api-key")
        .map_err(|e| format!("Keychain error: {}", e))?;
    entry
        .set_password(&key)
        .map_err(|e| format!("Failed to save key: {}", e))?;

    // Update in-memory state
    let mut api_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?;
    *api_key = Some(key);

    Ok(())
}
```

- [ ] **Step 4: Wire up lib.rs and main.rs**

Create `src-tauri/src/lib.rs`:

```rust
mod claude;
mod commands;
mod state;

use state::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            commands::send_message,
            commands::get_api_key_status,
            commands::set_api_key,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

Ensure `src-tauri/src/main.rs` calls into lib:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    soy_app_lib::run();
}
```

Note: The exact lib crate name depends on how Cargo.toml names the lib target. Check `src-tauri/Cargo.toml` for the `[lib]` section and use the correct crate name (likely `soy_app_lib` from the package name `soy-app`).

- [ ] **Step 5: Build and test**

```bash
cd soy-app
npm run tauri dev
```

Expected: App opens. No API key → typing a message shows error about missing key. If you set a key via the browser console (`invoke('set_api_key', { key: 'sk-ant-...' })`), messages should stream back from Claude.

- [ ] **Step 6: Add API key setup UX**

Update `src/App.tsx` to show an API key prompt when no key is set:

```tsx
import { useEffect, useState } from "react";
import { ChatPane } from "./components/chat/ChatPane";
import { useChat } from "./hooks/useChat";
import { getApiKeyStatus, setApiKey } from "./lib/commands";
import { KeyRound } from "lucide-react";

function App() {
  const { messages, isStreaming, send } = useChat();
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [keyInput, setKeyInput] = useState("");

  useEffect(() => {
    getApiKeyStatus().then((s) => setHasKey(s.hasKey));
  }, []);

  const handleSetKey = async () => {
    if (!keyInput.trim()) return;
    await setApiKey(keyInput.trim());
    setHasKey(true);
  };

  if (hasKey === null) return null; // loading

  if (!hasKey) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="max-w-md w-full px-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-zinc-100 mb-4">
              <KeyRound size={24} className="text-zinc-600" />
            </div>
            <h1 className="text-xl font-semibold text-zinc-900">Software of You</h1>
            <p className="text-sm text-zinc-500 mt-1">Enter your Claude API key to get started.</p>
          </div>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSetKey()}
            placeholder="sk-ant-..."
            className="w-full px-4 py-3 rounded-xl bg-zinc-100 text-sm outline-none focus:ring-2 focus:ring-zinc-300"
          />
          <button
            onClick={handleSetKey}
            className="w-full mt-3 px-4 py-3 rounded-xl bg-zinc-900 text-white text-sm font-medium hover:bg-zinc-700 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      <div className="flex-1 flex flex-col">
        <ChatPane messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
    </div>
  );
}

export default App;
```

- [ ] **Step 7: Test end-to-end**

```bash
npm run tauri dev
```

Expected: App opens → API key prompt → enter key → chat works → Claude streams responses in real-time with the typing cursor.

- [ ] **Step 8: Commit**

```bash
git add soy-app/
git commit -m "feat: Claude API streaming with keychain storage and chat UX"
```

---

## Phase 2: Data Layer (Make it smart)

**Goal:** SQLite database with migrations, tool executor, and Claude tool use loop. "Add a contact named Sarah" should work.

### Task 4: SQLite database manager

**Files:**
- Create: `src-tauri/src/db.rs`
- Create: `src-tauri/migrations/` (copy from `data/migrations/`)
- Modify: `src-tauri/src/state.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Copy and consolidate migrations**

Copy migration SQL files from the existing `data/migrations/` directory into `src-tauri/migrations/`. Renumber to remove gaps from modules not in v1. Create a new migration `016_conversations.sql` for chat history:

```sql
-- 016_conversations.sql
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    panel_hint TEXT,
    tool_calls TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
```

- [ ] **Step 2: Implement database manager**

Create `src-tauri/src/db.rs`:

```rust
use rusqlite::{params, Connection, Result as SqlResult};
use std::path::PathBuf;
use std::sync::Mutex;

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn new() -> Result<Self, String> {
        let db_path = Self::db_path();

        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create data dir: {}", e))?;
        }

        let conn = Connection::open(&db_path)
            .map_err(|e| format!("Failed to open database: {}", e))?;

        // Enable WAL mode for better concurrent reads
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
            .map_err(|e| format!("Failed to set pragmas: {}", e))?;

        let db = Self {
            conn: Mutex::new(conn),
        };
        db.run_migrations()?;
        Ok(db)
    }

    pub fn db_path() -> PathBuf {
        let data_dir = dirs::data_local_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("software-of-you");
        data_dir.join("soy.db")
    }

    fn run_migrations(&self) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        // Create migrations tracking table
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                applied_at TEXT DEFAULT (datetime('now'))
            )"
        ).map_err(|e| format!("Migration table error: {}", e))?;

        // Get list of applied migrations
        let mut stmt = conn
            .prepare("SELECT filename FROM _migrations")
            .map_err(|e| e.to_string())?;
        let applied: Vec<String> = stmt
            .query_map([], |row| row.get(0))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        // Read embedded migration files (sorted by name)
        let migrations_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("migrations");
        if !migrations_dir.exists() {
            return Ok(()); // No migrations dir yet
        }

        let mut entries: Vec<_> = std::fs::read_dir(&migrations_dir)
            .map_err(|e| format!("Can't read migrations dir: {}", e))?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().map_or(false, |ext| ext == "sql"))
            .collect();
        entries.sort_by_key(|e| e.file_name());

        for entry in entries {
            let filename = entry.file_name().to_string_lossy().to_string();
            if applied.contains(&filename) {
                continue;
            }

            let sql = std::fs::read_to_string(entry.path())
                .map_err(|e| format!("Can't read {}: {}", filename, e))?;

            conn.execute_batch(&sql)
                .map_err(|e| format!("Migration {} failed: {}", filename, e))?;

            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?1)",
                params![filename],
            )
            .map_err(|e| format!("Can't record migration {}: {}", filename, e))?;
        }

        Ok(())
    }

    /// Execute a query and return results as JSON array
    pub fn query_json(&self, sql: &str, params: &[&dyn rusqlite::ToSql]) -> Result<serde_json::Value, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let mut stmt = conn.prepare(sql).map_err(|e| format!("SQL error: {}", e))?;

        let column_names: Vec<String> = stmt
            .column_names()
            .iter()
            .map(|s| s.to_string())
            .collect();

        let rows: Vec<serde_json::Value> = stmt
            .query_map(params, |row| {
                let mut map = serde_json::Map::new();
                for (i, name) in column_names.iter().enumerate() {
                    let val = row.get_ref(i).unwrap_or(rusqlite::types::ValueRef::Null);
                    let json_val = match val {
                        rusqlite::types::ValueRef::Null => serde_json::Value::Null,
                        rusqlite::types::ValueRef::Integer(n) => serde_json::json!(n),
                        rusqlite::types::ValueRef::Real(f) => serde_json::json!(f),
                        rusqlite::types::ValueRef::Text(s) => {
                            serde_json::Value::String(String::from_utf8_lossy(s).to_string())
                        }
                        rusqlite::types::ValueRef::Blob(_) => serde_json::Value::Null,
                    };
                    map.insert(name.clone(), json_val);
                }
                Ok(serde_json::Value::Object(map))
            })
            .map_err(|e| format!("Query error: {}", e))?
            .filter_map(|r| r.ok())
            .collect();

        Ok(serde_json::Value::Array(rows))
    }

    /// Execute a write statement (INSERT, UPDATE, DELETE)
    pub fn execute(&self, sql: &str, params: &[&dyn rusqlite::ToSql]) -> Result<i64, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute(sql, params)
            .map_err(|e| format!("Execute error: {}", e))?;
        Ok(conn.last_insert_rowid())
    }
}
```

- [ ] **Step 3: Update AppState to include database**

Update `src-tauri/src/state.rs`:

```rust
use crate::db::Database;
use std::sync::{Arc, Mutex};

pub struct AppState {
    pub api_key: Mutex<Option<String>>,
    pub db: Arc<Database>,
}

impl AppState {
    pub fn new() -> Self {
        let key = keyring::Entry::new("com.softwareofyou.app", "claude-api-key")
            .ok()
            .and_then(|e| e.get_password().ok());

        let db = Database::new().expect("Failed to initialize database");

        Self {
            api_key: Mutex::new(key),
            db: Arc::new(db),
        }
    }
}
```

- [ ] **Step 4: Update lib.rs**

```rust
mod claude;
mod commands;
mod db;
mod state;
// tools module added in next task
```

- [ ] **Step 5: Test database initialization**

```bash
cd soy-app && npm run tauri dev
```

Expected: App starts without errors. Check that `~/.local/share/software-of-you/soy.db` exists and has tables:

```bash
sqlite3 ~/.local/share/software-of-you/soy.db ".tables"
```

- [ ] **Step 6: Commit**

```bash
git add soy-app/src-tauri/
git commit -m "feat: SQLite database manager with idempotent migrations"
```

---

### Task 5: Tool system + first tools (contacts, search, overview)

**Files:**
- Create: `src-tauri/src/tools/mod.rs`
- Create: `src-tauri/src/tools/contacts.rs`
- Create: `src-tauri/src/tools/search.rs`
- Create: `src-tauri/src/tools/overview.rs`
- Create: `src-tauri/src/tools/profile.rs`
- Create: `src-tauri/src/tools/system.rs`
- Create: `src-tauri/src/tools/inbox.rs`
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Create tool registry**

Create `src-tauri/src/tools/mod.rs`:

```rust
pub mod contacts;
pub mod inbox;
pub mod overview;
pub mod profile;
pub mod search;
pub mod system;

use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

/// Execute a tool by name with given arguments, return JSON result
pub fn execute_tool(db: &Arc<Database>, tool_name: &str, args: &Value) -> Result<Value, String> {
    match tool_name {
        "contacts" => contacts::execute(db, args),
        "search" => search::execute(db, args),
        "get_overview" => overview::execute(db),
        "get_profile" => profile::execute(db, args),
        "system_status" => system::execute(db, args),
        "inbox" => inbox::execute(db, args),
        _ => Err(format!("Unknown tool: {}", tool_name)),
    }
}

/// Return tool definitions for Claude API (JSON schemas)
pub fn tool_definitions() -> Vec<Value> {
    vec![
        contacts::definition(),
        search::definition(),
        overview::definition(),
        profile::definition(),
        system::definition(),
        inbox::definition(),
    ]
}
```

- [ ] **Step 2: Implement contacts tool**

Create `src-tauri/src/tools/contacts.rs`. This is the largest tool — it handles add, edit, list, find, get actions. Port the SQL queries from the Python implementation.

The implementation should:
- Parse `action` from args (add/edit/list/find/get)
- Execute the corresponding SQL queries using `db.query_json()` and `db.execute()`
- Return structured JSON matching the Python tool's return format
- Log to activity_log on mutations

See the tool reference (from the exploration agent) for exact SQL queries per action.

```rust
use crate::db::Database;
use serde_json::{json, Value};
use std::sync::Arc;

pub fn definition() -> Value {
    json!({
        "name": "contacts",
        "description": "Manage contacts: add, edit, list, find, or get detailed contact information with cross-references.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "edit", "list", "find", "get"],
                    "description": "The action to perform"
                },
                "name": { "type": "string" },
                "email": { "type": "string" },
                "phone": { "type": "string" },
                "company": { "type": "string" },
                "role": { "type": "string" },
                "contact_type": { "type": "string", "enum": ["individual", "company"] },
                "status": { "type": "string" },
                "notes": { "type": "string" },
                "contact_id": { "type": "integer" },
                "query": { "type": "string" }
            },
            "required": ["action"]
        }
    })
}

pub fn execute(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("action is required")?;

    match action {
        "add" => add_contact(db, args),
        "edit" => edit_contact(db, args),
        "list" => list_contacts(db, args),
        "find" => find_contacts(db, args),
        "get" => get_contact(db, args),
        _ => Err(format!("Unknown action: {}", action)),
    }
}

fn add_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let name = args["name"].as_str().unwrap_or("");
    let email = args["email"].as_str().unwrap_or("");
    let phone = args["phone"].as_str().unwrap_or("");
    let company = args["company"].as_str().unwrap_or("");
    let role = args["role"].as_str().unwrap_or("");
    let contact_type = args["contact_type"].as_str().unwrap_or("individual");
    let status = args["status"].as_str().unwrap_or("active");
    let notes = args["notes"].as_str().unwrap_or("");

    if name.is_empty() {
        return Err("name is required to add a contact".to_string());
    }

    // Check for duplicates
    let dupes = db.query_json(
        "SELECT id, name, email FROM contacts WHERE name LIKE ?1 OR (email = ?2 AND email != '')",
        &[&format!("%{}%", name), &email],
    )?;

    let id = db.execute(
        "INSERT INTO contacts (name, email, phone, company, role, type, status, notes, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, datetime('now'), datetime('now'))",
        &[&name, &email, &phone, &company, &role, &contact_type, &status, &notes],
    )?;

    // Log activity
    db.execute(
        "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
         VALUES ('contact', ?1, 'created', ?2, datetime('now'))",
        &[&id, &format!("Added contact: {}", name)],
    )?;

    let mut result = json!({
        "result": {
            "contact_id": id,
            "name": name,
            "company": company,
        },
        "_context": {
            "suggestions": ["Log an interaction with this contact", "Add a follow-up reminder"]
        }
    });

    if let Value::Array(ref d) = dupes {
        if !d.is_empty() {
            result["possible_duplicates"] = dupes;
        }
    }

    Ok(result)
}

fn edit_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let contact_id = args["contact_id"].as_i64().ok_or("contact_id required for edit")?;

    let mut sets = Vec::new();
    let mut values: Vec<Box<dyn rusqlite::ToSql>> = Vec::new();

    for field in &["name", "email", "phone", "company", "role", "status", "notes"] {
        if let Some(val) = args[field].as_str() {
            sets.push(format!("{} = ?", field));
            values.push(Box::new(val.to_string()));
        }
    }

    if sets.is_empty() {
        return Err("No fields to update".to_string());
    }

    sets.push("updated_at = datetime('now')".to_string());
    values.push(Box::new(contact_id));

    let sql = format!(
        "UPDATE contacts SET {} WHERE id = ?",
        sets.join(", ")
    );

    let params: Vec<&dyn rusqlite::ToSql> = values.iter().map(|v| v.as_ref()).collect();
    db.execute(&sql, &params)?;

    let contact = db.query_json(
        "SELECT * FROM contacts WHERE id = ?1",
        &[&contact_id],
    )?;

    Ok(json!({ "result": contact[0] }))
}

fn list_contacts(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let status = args["status"].as_str().unwrap_or("active");

    let contacts = db.query_json(
        "SELECT id, name, company, role, email, status, updated_at
         FROM contacts WHERE status = ?1 ORDER BY updated_at DESC",
        &[&status],
    )?;

    let count = if let Value::Array(ref arr) = contacts { arr.len() } else { 0 };

    Ok(json!({
        "result": contacts,
        "count": count
    }))
}

fn find_contacts(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let query = args["query"].as_str().or(args["name"].as_str()).unwrap_or("");
    let pattern = format!("%{}%", query);

    let contacts = db.query_json(
        "SELECT id, name, company, role, email, status FROM contacts
         WHERE name LIKE ?1 OR email LIKE ?1 OR company LIKE ?1
         ORDER BY CASE WHEN name LIKE ?1 THEN 0 ELSE 1 END
         LIMIT 20",
        &[&pattern],
    )?;

    let count = if let Value::Array(ref arr) = contacts { arr.len() } else { 0 };

    Ok(json!({
        "result": contacts,
        "count": count
    }))
}

fn get_contact(db: &Arc<Database>, args: &Value) -> Result<Value, String> {
    let contact_id = args["contact_id"].as_i64().ok_or("contact_id required for get")?;

    let contact = db.query_json(
        "SELECT * FROM contacts WHERE id = ?1",
        &[&contact_id],
    )?;

    if contact.as_array().map_or(true, |a| a.is_empty()) {
        return Err(format!("Contact {} not found", contact_id));
    }

    // Cross-references
    let interactions = db.query_json(
        "SELECT * FROM contact_interactions WHERE contact_id = ?1 ORDER BY occurred_at DESC LIMIT 10",
        &[&contact_id],
    )?;

    let follow_ups = db.query_json(
        "SELECT * FROM follow_ups WHERE contact_id = ?1 AND status = 'pending' ORDER BY due_date ASC",
        &[&contact_id],
    )?;

    let emails = db.query_json(
        "SELECT id, thread_id, subject, snippet, from_name, direction, received_at
         FROM emails WHERE contact_id = ?1 ORDER BY received_at DESC LIMIT 10",
        &[&contact_id],
    )?;

    Ok(json!({
        "result": contact[0],
        "cross_references": {
            "recent_interactions": interactions,
            "pending_follow_ups": follow_ups,
            "recent_emails": emails
        }
    }))
}
```

- [ ] **Step 3: Implement remaining v1 tools**

Create stub implementations for `search.rs`, `overview.rs`, `profile.rs`, `system.rs`, `inbox.rs`. Each should have:
- A `definition()` function returning the JSON schema
- An `execute()` function with the core SQL queries from the tool reference

For brevity, these follow the same pattern as contacts. The key SQL queries are documented in the tool reference from the exploration agent. Port them using `db.query_json()` and `db.execute()`.

Priority order for implementation:
1. `system.rs` — needed for onboarding detection
2. `profile.rs` — needed for user profile
3. `overview.rs` — needed for dashboard
4. `search.rs` — needed for cross-module search
5. `inbox.rs` — needed for quick capture

- [ ] **Step 4: Commit**

```bash
git add soy-app/src-tauri/src/tools/
git commit -m "feat: implement v1 tool system with contacts, search, overview, profile, system, inbox"
```

---

### Task 6: Claude tool use loop

**Files:**
- Modify: `src-tauri/src/claude.rs`
- Modify: `src-tauri/src/commands.rs`
- Modify: `src-tauri/src/state.rs`

- [ ] **Step 1: Rewrite claude.rs with tool use support**

Replace `src-tauri/src/claude.rs` with a version that handles the full tool use loop. The key architectural change: use **non-streaming for tool use turns** (simpler to parse), then **stream the final text response**.

```rust
use crate::db::Database;
use crate::tools;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use futures_util::StreamExt;

const CLAUDE_API_URL: &str = "https://api.anthropic.com/v1/messages";
const MODEL: &str = "claude-sonnet-4-20250514";
const MAX_TOOL_ROUNDS: usize = 10;

#[derive(Serialize, Clone)]
pub struct StreamEvent {
    pub token: Option<String>,
    pub done: Option<bool>,
    pub panel_hint: Option<Value>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ChatMessage {
    pub role: String,
    pub content: Value, // String for user, Array of content blocks for assistant/tool
}

pub async fn send_with_tools(
    app: &AppHandle,
    api_key: &str,
    messages: Vec<ChatMessage>,
    db: &Arc<Database>,
) -> Result<(), String> {
    let client = Client::new();
    let system_prompt = build_system_prompt(db);
    let tool_defs = tools::tool_definitions();
    let mut conversation = messages;

    // Tool use loop: keep calling Claude until we get a text-only response
    for _ in 0..MAX_TOOL_ROUNDS {
        // Make non-streaming request to check for tool use
        let request = json!({
            "model": MODEL,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": conversation,
            "tools": tool_defs,
        });

        let response = client
            .post(CLAUDE_API_URL)
            .header("x-api-key", api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| format!("API request failed: {}", e))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(format!("API error {}: {}", status, body));
        }

        let body: Value = response.json().await.map_err(|e| e.to_string())?;
        let stop_reason = body["stop_reason"].as_str().unwrap_or("");
        let content = body["content"].as_array().ok_or("No content in response")?;

        // Check if response contains tool use
        let tool_uses: Vec<&Value> = content
            .iter()
            .filter(|block| block["type"].as_str() == Some("tool_use"))
            .collect();

        if tool_uses.is_empty() || stop_reason != "tool_use" {
            // No tool use — stream any text blocks to frontend and we're done
            for block in content {
                if block["type"].as_str() == Some("text") {
                    if let Some(text) = block["text"].as_str() {
                        // Emit in chunks to simulate streaming feel
                        for chunk in text.as_bytes().chunks(20) {
                            let chunk_str = String::from_utf8_lossy(chunk);
                            let _ = app.emit("chat-stream", StreamEvent {
                                token: Some(chunk_str.to_string()),
                                done: None,
                                panel_hint: None,
                                error: None,
                            });
                            tokio::time::sleep(tokio::time::Duration::from_millis(15)).await;
                        }
                    }
                }
            }

            // Check for panel hints in the text
            let full_text: String = content
                .iter()
                .filter_map(|b| b["text"].as_str())
                .collect::<Vec<_>>()
                .join("");
            if let Some(hint) = extract_panel_hint(&full_text) {
                let _ = app.emit("chat-stream", StreamEvent {
                    token: None,
                    done: None,
                    panel_hint: Some(hint),
                    error: None,
                });
            }

            let _ = app.emit("chat-stream", StreamEvent {
                token: None,
                done: Some(true),
                panel_hint: None,
                error: None,
            });
            return Ok(());
        }

        // Has tool use — execute tools and continue the loop
        // First, add the assistant's response to conversation
        conversation.push(ChatMessage {
            role: "assistant".to_string(),
            content: json!(content),
        });

        // Execute each tool and build tool_result messages
        let mut tool_results: Vec<Value> = Vec::new();
        for tool_use in &tool_uses {
            let tool_name = tool_use["name"].as_str().unwrap_or("");
            let tool_id = tool_use["id"].as_str().unwrap_or("");
            let tool_input = &tool_use["input"];

            // Emit a status indicator so user sees something happening
            let _ = app.emit("chat-stream", StreamEvent {
                token: Some(format!("*Using {}...*\n", tool_name)),
                done: None,
                panel_hint: None,
                error: None,
            });

            let result = tools::execute_tool(db, tool_name, tool_input);

            let tool_result_content = match result {
                Ok(data) => json!([{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": serde_json::to_string(&data).unwrap_or_default()
                }]),
                Err(err) => json!([{
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "is_error": true,
                    "content": err
                }]),
            };

            if let Value::Array(arr) = tool_result_content {
                tool_results.extend(arr);
            }
        }

        // Add tool results as a user message
        conversation.push(ChatMessage {
            role: "user".to_string(),
            content: json!(tool_results),
        });

        // Loop continues — next iteration calls Claude again with tool results
    }

    Err("Too many tool use rounds".to_string())
}

/// Extract [PANEL:type:id] markers from Claude's response
fn extract_panel_hint(text: &str) -> Option<Value> {
    // Look for [PANEL:contact:5] or [PANEL:dashboard] patterns
    let re_pattern = "[PANEL:";
    if let Some(start) = text.find(re_pattern) {
        let rest = &text[start + re_pattern.len()..];
        if let Some(end) = rest.find(']') {
            let parts: Vec<&str> = rest[..end].split(':').collect();
            let panel_type = parts.first().copied().unwrap_or("");
            let entity_id = parts.get(1).and_then(|s| s.parse::<i64>().ok());
            return Some(json!({
                "type": panel_type,
                "entityId": entity_id,
            }));
        }
    }
    None
}

fn build_system_prompt(db: &Arc<Database>) -> String {
    // Load user profile from DB
    let profile = db.query_json(
        "SELECT key, value FROM user_profile WHERE category IN ('identity', 'preferences')",
        &[],
    ).unwrap_or(json!([]));

    let mut name = "there".to_string();
    let mut style = "concise".to_string();
    if let Value::Array(ref rows) = profile {
        for row in rows {
            match row["key"].as_str() {
                Some("name") => name = row["value"].as_str().unwrap_or("there").to_string(),
                Some("communication_style") => style = row["value"].as_str().unwrap_or("concise").to_string(),
                _ => {}
            }
        }
    }

    format!(r#"You are Software of You — a personal data platform running as a native Mac app.
The user's name is {name}. Communication style preference: {style}.

## Core Behavior
- Be the interface. Users talk naturally. You translate to tool calls. Present results conversationally.
- Always cross-reference: when showing a contact, check linked projects/emails/meetings.
- Suggest next actions after completing a request.
- Never expose raw SQL or tool calls unless asked.
- Never fabricate data. If you can't derive a number, say so.

## Panel Hints
When your response references a specific entity that would benefit from a visual panel, include a marker:
- Contact: [PANEL:contact:<id>]
- Dashboard: [PANEL:dashboard]
- Calendar: [PANEL:calendar]
- Meeting prep: [PANEL:meeting-prep:<event_id>]
- Nudges: [PANEL:nudges]
- Commitments: [PANEL:commitments]

Place the marker at the END of your response, on its own line. Only include one panel hint per response.

## Style
- {style}. No filler.
- Use markdown tables for lists of 3+ items.
- Dates in human-readable format ("3 days ago", "next Tuesday").
- Focus on what matters — don't dump every field."#)
}
```

- [ ] **Step 2: Update send_message command to pass DB**

Update `commands.rs`:

```rust
#[tauri::command]
pub async fn send_message(
    app: AppHandle,
    state: State<'_, AppState>,
    message: String,
) -> Result<String, String> {
    let api_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .clone()
        .ok_or_else(|| "No API key set. Please set your Claude API key first.".to_string())?;

    let db = state.db.clone();

    let messages = vec![claude::ChatMessage {
        role: "user".to_string(),
        content: serde_json::json!(message),
    }];

    claude::send_with_tools(&app, &api_key, messages, &db).await?;
    Ok("done".to_string())
}
```

- [ ] **Step 3: Test tool use end-to-end**

```bash
npm run tauri dev
```

Test: Type "Add a contact named Sarah Chen, VP Engineering at Acme Corp"
Expected: Claude calls the `contacts` tool with add action, returns confirmation in chat.

Test: Type "List my contacts"
Expected: Claude calls `contacts` with list action, shows results.

Test: Type "Search for Sarah"
Expected: Claude calls `search` or `contacts/find`, shows results.

- [ ] **Step 4: Commit**

```bash
git add soy-app/src-tauri/src/
git commit -m "feat: Claude tool use loop — tools execute against SQLite"
```

---

### Task 7: Remaining v1 tools (interactions, email, calendar, transcripts, intelligence)

**Files:**
- Create: `src-tauri/src/tools/interactions.rs`
- Create: `src-tauri/src/tools/email.rs`
- Create: `src-tauri/src/tools/calendar.rs`
- Create: `src-tauri/src/tools/transcripts.rs`
- Create: `src-tauri/src/tools/intelligence.rs`
- Modify: `src-tauri/src/tools/mod.rs`

- [ ] **Step 1: Implement interactions tool**

Port from the Python reference: log, list, follow_up, complete_follow_up, list_follow_ups actions. Key patterns: contact resolution by ID or name, overdue computation, activity logging.

- [ ] **Step 2: Implement email tool**

Port: inbox, unread, search, from, thread actions. Note: this queries locally cached emails (synced in Phase 4). Without Google sync, the emails table will be empty — that's fine.

- [ ] **Step 3: Implement calendar tool**

Port: today, tomorrow, week, schedule, with, free actions. Same as email — works against cached data.

- [ ] **Step 4: Implement transcripts tool**

Port: import, add_analysis, list, get, commitments, complete_commitment actions. The two-step import flow (import raw → Claude analyzes → add_analysis stores results) is the most complex pattern.

- [ ] **Step 5: Implement intelligence tool**

Port: meeting_prep, nudges, commitments_view, relationship_pulse, weekly_review. These rely heavily on computed views (v_contact_health, v_nudge_items, etc.) — make sure those views are in the migrations.

- [ ] **Step 6: Register all tools in mod.rs**

Update `tools/mod.rs` to include all new tools in `execute_tool()` and `tool_definitions()`.

- [ ] **Step 7: Test**

```bash
npm run tauri dev
```

Test: "Log a call with Sarah — discussed Q2 roadmap, she raised timeline concerns"
Expected: Claude calls interactions/log, confirms the interaction was logged.

Test: "What are my nudges?"
Expected: Claude calls nudges tool (will be sparse with little data, but should work).

- [ ] **Step 8: Commit**

```bash
git add soy-app/src-tauri/src/tools/
git commit -m "feat: implement all v1 tools — interactions, email, calendar, transcripts, intelligence"
```

---

## Phase 3: Panel System (Make it visual)

**Goal:** The contextual side panel slides out with entity pages, dashboards, and composed views.

### Task 7b: InlineCard component + chat card rendering

**Files:**
- Create: `src/components/chat/InlineCard.tsx`
- Modify: `src/components/chat/MessageBubble.tsx`

- [ ] **Step 1: Create InlineCard component**

InlineCards are rich, tappable components embedded in assistant messages. They render when Claude's response contains structured data (contact mentions, meeting briefs, nudge summaries).

```tsx
// src/components/chat/InlineCard.tsx
import { ChevronRight } from "lucide-react";
import { PanelHint } from "../../lib/types";

interface InlineCardProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  panelHint?: PanelHint;
  onOpenPanel?: (hint: PanelHint) => void;
  children?: React.ReactNode;
}

export function InlineCard({ title, subtitle, icon, panelHint, onOpenPanel, children }: InlineCardProps) {
  return (
    <div
      className={`my-3 rounded-xl border border-zinc-200 bg-white p-4 ${
        panelHint ? "cursor-pointer hover:border-zinc-300 hover:shadow-sm transition-all" : ""
      }`}
      onClick={() => panelHint && onOpenPanel?.(panelHint)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {icon && <div className="text-zinc-500">{icon}</div>}
          <div>
            <p className="text-sm font-medium text-zinc-900">{title}</p>
            {subtitle && <p className="text-xs text-zinc-500">{subtitle}</p>}
          </div>
        </div>
        {panelHint && <ChevronRight size={16} className="text-zinc-400" />}
      </div>
      {children && <div className="mt-3 text-sm text-zinc-600">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Update MessageBubble to accept onOpenPanel callback**

Pass an `onOpenPanel` prop through from ChatPane so InlineCards can trigger the side panel. The MessageBubble component should detect when the assistant's markdown contains panel hint markers and render InlineCards for them.

- [ ] **Step 3: Commit**

```bash
git add soy-app/src/components/chat/
git commit -m "feat: InlineCard component for rich tappable cards in chat"
```

---

### Task 8: Side panel infrastructure

**Files:**
- Create: `src/hooks/usePanel.ts`
- Create: `src/components/panel/SidePanel.tsx`
- Create: `src/components/panel/PanelRouter.tsx`
- Create: `src/components/panel/EmptyState.tsx`
- Modify: `src/App.tsx`
- Modify: `src/hooks/useChat.ts`

- [ ] **Step 1: Create usePanel hook**

```typescript
import { useState, useCallback } from "react";
import { PanelHint } from "../lib/types";

export function usePanel() {
  const [panel, setPanel] = useState<PanelHint | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const showPanel = useCallback((hint: PanelHint) => {
    setPanel(hint);
    setIsOpen(true);
  }, []);

  const closePanel = useCallback(() => {
    if (!isPinned) {
      setIsOpen(false);
      setPanel(null);
    }
  }, [isPinned]);

  const togglePin = useCallback(() => {
    setIsPinned((p) => !p);
  }, []);

  return { panel, isOpen, isPinned, showPanel, closePanel, togglePin };
}
```

- [ ] **Step 2: Create SidePanel container with slide animation**

```tsx
import { X, Pin } from "lucide-react";
import { PanelHint } from "../../lib/types";
import { PanelRouter } from "./PanelRouter";

interface SidePanelProps {
  panel: PanelHint | null;
  isOpen: boolean;
  isPinned: boolean;
  onClose: () => void;
  onTogglePin: () => void;
}

export function SidePanel({ panel, isOpen, isPinned, onClose, onTogglePin }: SidePanelProps) {
  return (
    <div
      className={`border-l border-zinc-200 bg-white transition-all duration-300 ease-in-out overflow-hidden ${
        isOpen ? "w-[480px]" : "w-0"
      }`}
    >
      {panel && (
        <div className="h-full flex flex-col w-[480px]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
            <h2 className="text-sm font-semibold text-zinc-700">
              {panel.title || panel.type}
            </h2>
            <div className="flex items-center gap-1">
              <button
                onClick={onTogglePin}
                className={`p-1.5 rounded-lg hover:bg-zinc-100 ${isPinned ? "text-blue-600" : "text-zinc-400"}`}
              >
                <Pin size={14} />
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400">
                <X size={14} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <PanelRouter panel={panel} />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create PanelRouter (placeholder)**

```tsx
import { PanelHint } from "../../lib/types";
import { EmptyState } from "./EmptyState";

interface PanelRouterProps {
  panel: PanelHint;
}

export function PanelRouter({ panel }: PanelRouterProps) {
  // Components will be added in subsequent tasks
  switch (panel.type) {
    case "dashboard":
      return <EmptyState message="Dashboard coming soon" />;
    case "contact":
      return <EmptyState message={`Contact #${panel.entityId}`} />;
    case "calendar":
      return <EmptyState message="Calendar coming soon" />;
    default:
      return <EmptyState message={`Unknown panel: ${panel.type}`} />;
  }
}
```

- [ ] **Step 4: Wire panel into App.tsx**

Update `src/App.tsx` to include the side panel and connect it to chat panel hints:

```tsx
import { useEffect } from "react";
import { ChatPane } from "./components/chat/ChatPane";
import { SidePanel } from "./components/panel/SidePanel";
import { useChat } from "./hooks/useChat";
import { usePanel } from "./hooks/usePanel";
// ... keep existing API key setup code

// In the main render (after API key check):
const { messages, isStreaming, send, pendingPanelHint, setPendingPanelHint } = useChat();
const { panel, isOpen, isPinned, showPanel, closePanel, togglePin } = usePanel();

// React to panel hints from chat
useEffect(() => {
  if (pendingPanelHint) {
    showPanel(pendingPanelHint);
    setPendingPanelHint(null);
  }
}, [pendingPanelHint, showPanel, setPendingPanelHint]);

return (
  <div className="h-screen flex">
    <div className="flex-1 flex flex-col min-w-0">
      <ChatPane messages={messages} isStreaming={isStreaming} onSend={send} />
    </div>
    <SidePanel
      panel={panel}
      isOpen={isOpen}
      isPinned={isPinned}
      onClose={closePanel}
      onTogglePin={togglePin}
    />
  </div>
);
```

- [ ] **Step 5: Parse panel hints from Claude responses**

Update the Claude streaming handler in Rust to detect `[PANEL:type:id]` markers in the response text. When found:
- Strip the marker from the visible text
- Emit a `chat-stream` event with `panel_hint` set

Alternatively, handle this in the system prompt by instructing Claude to include a JSON block at the end of relevant responses.

- [ ] **Step 6: Test**

```bash
npm run tauri dev
```

Test: Type "Show my dashboard"
Expected: Panel slides out from the right showing the placeholder "Dashboard coming soon".

- [ ] **Step 7: Commit**

```bash
git add soy-app/src/
git commit -m "feat: side panel infrastructure with slide animation and pin"
```

---

### Task 9: Panel components

**Files:**
- Create: `src/components/panel/StatCard.tsx`
- Create: `src/components/panel/StatGrid.tsx`
- Create: `src/components/panel/ContactCard.tsx`
- Create: `src/components/panel/ContactList.tsx`
- Create: `src/components/panel/EntityPage.tsx`
- Create: `src/components/panel/Dashboard.tsx`
- Create: `src/components/panel/Timeline.tsx`
- Create: `src/components/panel/EmailList.tsx`
- Create: `src/components/panel/CalendarWeek.tsx`
- Create: `src/components/panel/CommitmentList.tsx`
- Create: `src/components/panel/NudgeFeed.tsx`
- Create: `src/components/panel/MeetingPrep.tsx`
- Create: `src/components/panel/Settings.tsx`
- Create: `src/components/shared/Avatar.tsx`
- Create: `src/components/shared/Badge.tsx`
- Create: `src/components/shared/Card.tsx`
- Modify: `src/components/panel/PanelRouter.tsx`
- Modify: `src/lib/commands.ts` (add panel data fetchers)

- [ ] **Step 1: Create shared primitives (Avatar, Badge, Card)**

These are small reusable components used across all panel views:
- `Avatar` — circular initials badge with generated color
- `Badge` — status/urgency labels (urgent = red, soon = amber, etc.)
- `Card` — base card wrapper with rounded corners, shadow, padding

- [ ] **Step 2: Create StatCard and StatGrid**

```tsx
// StatCard: single metric with label, value, optional trend
// StatGrid: responsive grid of StatCards
```

- [ ] **Step 3: Create EntityPage (contact detail)**

The contact entity page is the richest panel view. It shows:
- Contact info header (avatar, name, company, role)
- Stat grid (emails, interactions, days silent, relationship score)
- Open commitments list
- Recent emails
- Upcoming meetings
- Timeline of interactions

Fetch data via a Tauri command `get_panel_data` that calls `profile::execute()` and returns the full cross-referenced data.

- [ ] **Step 4: Create Dashboard**

The dashboard shows:
- Stat grid (contacts, emails, meetings today, nudges)
- Today's calendar
- Overdue items
- Recent activity

Fetch data via `overview::execute()`.

- [ ] **Step 5: Create remaining panel components**

- `Timeline` — chronological list with date grouping
- `EmailList` — email rows with subject, sender, date, read status
- `CalendarWeek` — day columns with event blocks
- `CommitmentList` — commitments with owner, due date, urgency badge
- `NudgeFeed` — nudge items grouped by urgency tier
- `MeetingPrep` — attendee briefs, open threads, suggested opener
- `Settings` — API key management, data location, Google connection

- [ ] **Step 6: Wire PanelRouter to all components**

Update `PanelRouter.tsx` to route each panel type to its component with the appropriate data fetching.

- [ ] **Step 7: Add Tauri commands for panel data**

Add `get_panel_data` command in Rust that takes a panel type + entity ID and returns the data needed by the component. This calls the appropriate tool functions internally.

- [ ] **Step 8: Test**

```bash
npm run tauri dev
```

Test: Add a contact, then "tell me about Sarah" → entity page should appear in panel with real data.
Test: "Show my dashboard" → dashboard appears with stats.

- [ ] **Step 9: Commit**

```bash
git add soy-app/src/
git commit -m "feat: panel components — entity page, dashboard, timeline, email, calendar, nudges"
```

---

### Task 9b: Component composition engine

**Files:**
- Create: `src/components/panel/CompositionRenderer.tsx`
- Modify: `src/components/panel/PanelRouter.tsx`
- Modify: `src/lib/commands.ts`

- [ ] **Step 1: Create CompositionRenderer**

This renders the JSON layout specs that Claude returns for "show me X" requests:

```tsx
// src/components/panel/CompositionRenderer.tsx
import { CompositionSpec, ComponentSpec } from "../../lib/types";
import { StatGrid } from "./StatGrid";
import { Timeline } from "./Timeline";
import { EmailList } from "./EmailList";
import { CommitmentList } from "./CommitmentList";
import { ContactList } from "./ContactList";
import { NudgeFeed } from "./NudgeFeed";
import { EmptyState } from "./EmptyState";

const COMPONENT_REGISTRY: Record<string, React.ComponentType<any>> = {
  "stat-grid": StatGrid,
  "timeline": Timeline,
  "email-list": EmailList,
  "commitment-list": CommitmentList,
  "contact-list": ContactList,
  "nudge-feed": NudgeFeed,
};

interface CompositionRendererProps {
  spec: CompositionSpec;
}

export function CompositionRenderer({ spec }: CompositionRendererProps) {
  const renderComponent = (comp: ComponentSpec, index: number) => {
    const Component = COMPONENT_REGISTRY[comp.type];
    if (!Component) {
      return <EmptyState key={index} message={`Unknown component: ${comp.type}`} />;
    }
    return <Component key={index} {...comp.props} />;
  };

  if (spec.layout === "two-column") {
    return (
      <div className="grid grid-cols-2 gap-4">
        {spec.components.map(renderComponent)}
      </div>
    );
  }

  // Default: stacked
  return (
    <div className="flex flex-col gap-4">
      {spec.components.map(renderComponent)}
    </div>
  );
}
```

- [ ] **Step 2: Wire into PanelRouter**

Add a `"composition"` case to PanelRouter that renders `CompositionRenderer` with the panel hint's `composition` spec.

- [ ] **Step 3: Add Tauri command for composition data**

The Rust backend needs a `get_composition_data` command that takes a `CompositionSpec`, executes the queries for each component's `props`, and returns hydrated data. This keeps data fetching on the backend.

- [ ] **Step 4: Commit**

```bash
git add soy-app/src/
git commit -m "feat: component composition engine for dynamic panel views"
```

---

## Phase 4: Google Integration

**Goal:** OAuth flow + Gmail/Calendar sync populating the emails and calendar_events tables.

### Task 10: Google OAuth

**Files:**
- Create: `src-tauri/src/google/mod.rs`
- Create: `src-tauri/src/google/oauth.rs`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/src/commands.rs`
- Modify: `src-tauri/tauri.conf.json` (add deep link scheme)

- [ ] **Step 1: Register deep link scheme**

Add to `tauri.conf.json` under plugins:

```json
{
  "plugins": {
    "deep-link": {
      "desktop": {
        "schemes": ["soy"]
      }
    }
  }
}
```

Add the deep-link plugin to `Cargo.toml`:

```toml
tauri-plugin-deep-link = "2"
```

- [ ] **Step 2: Implement OAuth2 + PKCE flow**

`src-tauri/src/google/oauth.rs`:
- Generate PKCE challenge
- Open browser to Google's OAuth URL with `redirect_uri=soy://auth/callback`
- Listen for the deep link callback
- Exchange code for tokens
- Store refresh token in Keychain
- Store access token in memory

Google OAuth scopes needed (same as existing):
- `gmail.readonly`
- `gmail.send`
- `calendar.readonly`
- `calendar.events`
- `userinfo.email`

- [ ] **Step 3: Add connect/disconnect commands**

Add Tauri commands:
- `connect_google` — initiates OAuth flow
- `disconnect_google` — revokes token, removes from Keychain
- `get_google_status` — checks if connected

- [ ] **Step 4: Test OAuth flow**

Note: Requires a Google Cloud project with OAuth credentials configured for desktop app with `soy://auth/callback` as redirect URI.

- [ ] **Step 5: Commit**

```bash
git add soy-app/src-tauri/src/google/
git commit -m "feat: Google OAuth2 + PKCE via Tauri deep links"
```

---

### Task 11: Gmail + Calendar sync

**Files:**
- Create: `src-tauri/src/google/gmail.rs`
- Create: `src-tauri/src/google/calendar.rs`
- Modify: `src-tauri/src/commands.rs`

- [ ] **Step 1: Implement Gmail sync**

`src-tauri/src/google/gmail.rs`:
- Fetch recent messages from Gmail API (last 50)
- Parse message headers (From, To, Subject, Date)
- Extract snippet
- Match sender/recipient to contacts by email address
- INSERT OR REPLACE into `emails` table
- Update `soy_meta` with `gmail_last_synced` timestamp

- [ ] **Step 2: Implement Calendar sync**

`src-tauri/src/google/calendar.rs`:
- Fetch events from Google Calendar API (last 7 days + next 14 days)
- Parse event data (title, start, end, location, attendees)
- Match attendees to contacts by email
- INSERT OR REPLACE into `calendar_events` table
- Update `soy_meta` with `calendar_last_synced` timestamp

- [ ] **Step 3: Add auto-sync timer**

Set up a background task that runs sync every 15 minutes when the app is active. Use `tokio::spawn` with a timer.

- [ ] **Step 4: Wire sync into tool execution**

Update tools that need fresh data (email, calendar, intelligence) to check staleness and trigger sync before querying.

- [ ] **Step 5: Test**

Connect Google → verify emails appear in the database → "Show me recent emails" should work.

- [ ] **Step 6: Commit**

```bash
git add soy-app/src-tauri/src/google/
git commit -m "feat: Gmail + Calendar sync with auto-refresh timer"
```

---

## Phase 5: Polish + Menu Bar

**Goal:** Menu bar mode, onboarding flow, conversation persistence, settings, error handling.

### Task 12: Menu bar mode

**Files:**
- Create: `src/components/menubar/MenuBarWindow.tsx`
- Modify: `src-tauri/src/lib.rs` (create tray + secondary window)
- Modify: `src-tauri/tauri.conf.json` (add tray config)

- [ ] **Step 1: Configure Tauri tray**

Add tray configuration to create a menu bar icon. Use Tauri v2's `tray` plugin.

Add to `Cargo.toml`:
```toml
tauri-plugin-positioner = "2"
```

- [ ] **Step 2: Create menu bar window**

Create a secondary Tauri window (compact, ~320x400px) that appears when the tray icon is clicked. Positioned below the tray icon using the positioner plugin.

- [ ] **Step 3: Build MenuBarWindow component**

Show:
- Nudge count badges (urgent/soon)
- Next meeting
- Emails needing reply
- Quick text input
- "Open full window" button

Data comes from `overview::execute()` and `intelligence::nudges()`.

- [ ] **Step 4: Test**

Click menu bar icon → popover appears with nudges and quick input.

- [ ] **Step 5: Commit**

```bash
git add soy-app/
git commit -m "feat: menu bar mode with nudges, quick input, and tray icon"
```

---

### Task 13: Onboarding flow

**Files:**
- Modify: `src-tauri/src/claude.rs` (onboarding system prompt variant)
- Modify: `src/App.tsx` (detect first-run state)

- [ ] **Step 1: Detect first-run state**

On app launch, check:
```sql
SELECT COUNT(*) FROM contacts;
SELECT COUNT(*) FROM user_profile WHERE category = 'identity';
```

If no identity rows → show onboarding system prompt to Claude.

- [ ] **Step 2: Build onboarding system prompt**

A special system prompt variant that instructs Claude to:
1. Welcome the user with the SoY greeting
2. Ask their name
3. Ask role, focus, communication style
4. Store answers in user_profile table
5. Transition to data prompts

This uses the same chat UI — the onboarding IS the first conversation.

- [ ] **Step 3: Test**

Delete the database → relaunch → verify onboarding conversation flows correctly.

- [ ] **Step 4: Commit**

```bash
git add soy-app/
git commit -m "feat: first-run onboarding as a guided chat conversation"
```

---

### Task 14: Conversation persistence

**Files:**
- Modify: `src-tauri/src/commands.rs`
- Modify: `src-tauri/src/claude.rs`
- Modify: `src/hooks/useChat.ts`

- [ ] **Step 1: Save messages to database**

After each message (user or assistant), INSERT into the `messages` table with the `conversation_id`.

Create a new conversation on app launch. Set `title` from the first user message (first 50 chars).

- [ ] **Step 2: Load conversation history on launch**

On app start, load the most recent conversation's messages from the database and populate the chat.

- [ ] **Step 3: Include conversation history in Claude API calls**

Send the recent message history (last N messages that fit in context) to Claude with each API call, not just the latest user message.

- [ ] **Step 4: Test**

Send messages → close app → reopen → verify messages are preserved.

- [ ] **Step 5: Commit**

```bash
git add soy-app/
git commit -m "feat: conversation persistence — chat history survives app restarts"
```

---

### Task 15: Settings panel + error handling

**Files:**
- Create: `src/components/panel/Settings.tsx`
- Modify: `src/components/panel/PanelRouter.tsx`
- Modify: `src-tauri/src/commands.rs`

- [ ] **Step 1: Build Settings panel**

Settings rendered in the side panel when user says "open settings" or hits Cmd+,:
- Claude API key (show masked, allow change)
- Google account (connect/disconnect button + status)
- User profile (name, role, communication style — editable)
- Data location (show path, backup button)
- About (version, links)

- [ ] **Step 2: Add keyboard shortcut for settings**

Register `Cmd+,` as a global shortcut that emits a panel hint for settings.

- [ ] **Step 3: Implement error handling**

Add error states throughout:
- No internet → show banner, allow local browsing
- Claude API key invalid → prompt to check in settings
- Google token expired → silent refresh, banner if fails
- Database error → show error in chat

- [ ] **Step 4: Test error scenarios**

- Remove API key → verify error message
- Disconnect internet → verify graceful degradation
- Invalid API key → verify helpful error

- [ ] **Step 5: Commit**

```bash
git add soy-app/
git commit -m "feat: settings panel, keyboard shortcuts, and error handling"
```

---

### Task 16: Final polish

**Files:**
- Various UI tweaks across components

- [ ] **Step 1: App icon**

Create or generate a 1024x1024 app icon. Run Tauri's icon generator:
```bash
cd soy-app
npm run tauri icon path/to/icon.png
```

- [ ] **Step 2: Window chrome**

- Add a thin title bar area for dragging (Tauri `decorations: false` + custom drag region)
- Or keep native title bar for v1 simplicity

- [ ] **Step 3: Loading states**

Add loading spinners/skeletons for:
- Panel data loading
- Initial app startup
- Google sync in progress

- [ ] **Step 4: Empty states**

All panel components should show friendly empty states when no data exists (e.g., "No contacts yet. Try: 'Add a contact named...'").

- [ ] **Step 5: Build for release**

```bash
cd soy-app
npm run tauri build
```

This produces a `.dmg` and `.app` in `src-tauri/target/release/bundle/`.

- [ ] **Step 6: Test the built app**

Open the `.app` from Finder (not dev mode). Verify:
- Database creates correctly
- API key entry works
- Chat + tools work
- Panel slides out
- Menu bar mode works
- Google OAuth works (if configured)

- [ ] **Step 7: Commit**

```bash
git add soy-app/
git commit -m "feat: app icon, polish, and release build"
```

---

## Implementation Notes

**Migration strategy:** Copy all 24 existing migration files from `data/migrations/` into `src-tauri/migrations/` with their original filenames. Add `025_conversations.sql` as the new migration for chat history. The migration runner processes files in alphabetical order, so numbering is preserved.

**Lib crate name:** The Tauri scaffold sets the `[lib]` crate name based on the package name in `Cargo.toml`. For a package named `soy-app`, the lib crate will be `soy_app`. Update `main.rs` to `soy_app::run()`. Verify after scaffolding.

**CSS file path:** The Tauri React-TS scaffold produces `src/styles.css`. Rename to `src/styles/globals.css` during Task 1 Step 3 and update the import in `main.tsx` accordingly.

**build.rs:** Generated by the Tauri scaffold — no manual creation needed.

**Conversation history in API calls:** Task 14 Step 3 should maintain a rolling window of messages. Count tokens approximately (4 chars ≈ 1 token). When the conversation exceeds ~100K tokens, summarize the older half by calling Claude with a "summarize this conversation" prompt, then replace the detailed messages with the summary. This keeps the context fresh without hitting limits.

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| 1: Shell + Chat | 1-3 | Tauri window, chat UI, Claude streaming |
| 2: Data Layer | 4-7 | SQLite, all 11 tools, tool use loop |
| 3: Panel System | 7b, 8, 9, 9b | InlineCards, side panel, 14 component types, composition engine |
| 4: Google Integration | 10-11 | OAuth, Gmail sync, Calendar sync |
| 5: Polish | 12-16 | Menu bar, onboarding, persistence, settings, release build |

**Parallel opportunities:** Tasks 7b-9b (frontend) can be built in parallel with Task 7 (remaining tools) since they're frontend vs backend. Tasks 10-11 (Google) are independent of the panel system.
