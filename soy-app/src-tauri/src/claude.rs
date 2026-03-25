use crate::db::Database;
use crate::google;
use crate::state::AppState;
use crate::tools;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager};

const CLAUDE_API_URL: &str = "https://api.anthropic.com/v1/messages";
const MODEL: &str = "claude-sonnet-4-20250514";
const MAX_TOOL_ROUNDS: usize = 10;

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
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
    conversation_id: Option<i64>,
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

        let response = match client
            .post(CLAUDE_API_URL)
            .header("x-api-key", api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&request)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(e) => {
                if e.is_connect() || e.is_timeout() {
                    return Err(
                        "Can't reach Claude. Check your internet connection.".to_string(),
                    );
                }
                return Err(format!("Network error: {}", e));
            }
        };

        if !response.status().is_success() {
            let status = response.status().as_u16();
            let _body = response.text().await.unwrap_or_default();
            return Err(match status {
                401 => "Your API key appears to be invalid. Check Settings (\u{2318},) to update it.".to_string(),
                429 => "Rate limited. Please wait a moment and try again.".to_string(),
                500..=599 => "Claude is having trouble right now. Try again in a few seconds.".to_string(),
                _ => format!("API error ({}). Please try again.", status),
            });
        }

        let body: Value = response.json().await.map_err(|e| e.to_string())?;
        let stop_reason = body["stop_reason"].as_str().unwrap_or("");
        let content = body["content"]
            .as_array()
            .ok_or("No content in response")?;

        // Check if response contains tool use
        let tool_uses: Vec<&Value> = content
            .iter()
            .filter(|block| block["type"].as_str() == Some("tool_use"))
            .collect();

        if tool_uses.is_empty() || stop_reason != "tool_use" {
            // Collect full text and extract panel hint before streaming
            let full_text: String = content
                .iter()
                .filter_map(|b| b["text"].as_str())
                .collect::<Vec<_>>()
                .join("");

            let panel_hint = extract_panel_hint(&full_text);

            // Strip [PANEL:...] markers so they aren't visible to the user
            let display_text = strip_panel_markers(&full_text);

            // Save the final assistant response to DB (with full text, before stripping)
            if let Some(conv_id) = conversation_id {
                let _ = db.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (?1, 'assistant', ?2)",
                    &[&conv_id as &dyn rusqlite::ToSql, &display_text as &dyn rusqlite::ToSql],
                );
            }

            // Emit cleaned text in chunks to simulate streaming feel
            if !display_text.is_empty() {
                for chunk in display_text.as_bytes().chunks(20) {
                    let chunk_str = String::from_utf8_lossy(chunk);
                    let _ = app.emit(
                        "chat-stream",
                        StreamEvent {
                            token: Some(chunk_str.to_string()),
                            done: None,
                            panel_hint: None,
                            error: None,
                        },
                    );
                    tokio::time::sleep(tokio::time::Duration::from_millis(15)).await;
                }
            }

            // Emit done + panel hint together in a single event to avoid
            // race conditions where done arrives first and the listener
            // unsubscribes before the panel hint event is processed.
            let _ = app.emit(
                "chat-stream",
                StreamEvent {
                    token: None,
                    done: Some(true),
                    panel_hint,
                    error: None,
                },
            );
            return Ok(());
        }

        // Has tool use — execute tools and continue the loop
        // First, add the assistant's response to conversation
        let assistant_content = json!(content);
        conversation.push(ChatMessage {
            role: "assistant".to_string(),
            content: assistant_content.clone(),
        });

        // Persist the assistant tool-use message so future turns have context
        if let Some(conv_id) = conversation_id {
            let content_str = serde_json::to_string(&assistant_content).unwrap_or_default();
            let _ = db.execute(
                "INSERT INTO messages (conversation_id, role, content, tool_calls) VALUES (?1, 'assistant', ?2, ?2)",
                &[&conv_id as &dyn rusqlite::ToSql, &content_str],
            );
        }

        // Execute each tool and build tool_result messages
        let mut tool_results: Vec<Value> = Vec::new();
        for tool_use in &tool_uses {
            let tool_name = tool_use["name"].as_str().unwrap_or("");
            let tool_id = tool_use["id"].as_str().unwrap_or("");
            let tool_input = &tool_use["input"];

            // Emit a status indicator so user sees something happening
            let _ = app.emit(
                "chat-stream",
                StreamEvent {
                    token: Some(format!("*Using {}...*\n", tool_name)),
                    done: None,
                    panel_hint: None,
                    error: None,
                },
            );

            // The `google` tool is async (needs network + AppState), handle it separately
            let result = if tool_name == "google" {
                execute_google_tool(app, db, tool_input).await
            } else {
                tools::execute_tool(db, tool_name, tool_input)
            };

            let tool_result = match result {
                Ok(data) => json!({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": serde_json::to_string(&data).unwrap_or_default()
                }),
                Err(err) => json!({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "is_error": true,
                    "content": err
                }),
            };

            tool_results.push(tool_result);
        }

        let tool_results_content = json!(tool_results);

        // Persist the tool results so future turns have context
        if let Some(conv_id) = conversation_id {
            let content_str = serde_json::to_string(&tool_results_content).unwrap_or_default();
            let _ = db.execute(
                "INSERT INTO messages (conversation_id, role, content, tool_calls) VALUES (?1, 'user', ?2, ?2)",
                &[&conv_id as &dyn rusqlite::ToSql, &content_str],
            );
        }

        // Add tool results as a user message
        conversation.push(ChatMessage {
            role: "user".to_string(),
            content: tool_results_content,
        });

        // Loop continues — next iteration calls Claude again with tool results
    }

    Err("Too many tool use rounds".to_string())
}

/// Extract [PANEL:type:id] markers from Claude's response
fn extract_panel_hint(text: &str) -> Option<Value> {
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

/// Strip [PANEL:...] markers from text so they aren't shown to the user
fn strip_panel_markers(text: &str) -> String {
    let mut result = text.to_string();
    while let Some(start) = result.find("[PANEL:") {
        if let Some(end) = result[start..].find(']') {
            // Remove the marker and any surrounding whitespace/newline
            let marker_end = start + end + 1;
            // If the marker is on its own line, remove the whole line
            let remove_start = if start > 0 && result.as_bytes()[start - 1] == b'\n' {
                start - 1
            } else {
                start
            };
            result = format!("{}{}", &result[..remove_start], &result[marker_end..]);
        } else {
            break;
        }
    }
    result.trim_end().to_string()
}

/// Execute the async `google` tool — handles connect, sync, and status actions.
/// This runs outside the normal sync tool execution path because it needs
/// network access and the AppState for token management.
async fn execute_google_tool(
    app: &AppHandle,
    db: &Arc<Database>,
    args: &Value,
) -> Result<Value, String> {
    let action = args["action"].as_str().ok_or("Missing action")?;
    let state = app.state::<AppState>();

    match action {
        "status" => {
            let connected = google::oauth::is_connected(db);
            let email = google::oauth::load_primary_email(db)?.unwrap_or_default();
            let gmail_synced = db
                .query_json(
                    "SELECT value FROM soy_meta WHERE key = 'gmail_last_synced'",
                    &[],
                )
                .ok()
                .and_then(|v| v[0]["value"].as_str().map(String::from));
            let calendar_synced = db
                .query_json(
                    "SELECT value FROM soy_meta WHERE key = 'calendar_last_synced'",
                    &[],
                )
                .ok()
                .and_then(|v| v[0]["value"].as_str().map(String::from));
            let email_count: i64 = db
                .query_json("SELECT COUNT(*) as count FROM emails", &[])
                .and_then(|v| v[0]["count"].as_i64().ok_or_else(|| "no count".into()))
                .unwrap_or(0);
            let event_count: i64 = db
                .query_json("SELECT COUNT(*) as count FROM calendar_events", &[])
                .and_then(|v| v[0]["count"].as_i64().ok_or_else(|| "no count".into()))
                .unwrap_or(0);

            Ok(json!({
                "connected": connected,
                "email": email,
                "gmail_last_synced": gmail_synced,
                "calendar_last_synced": calendar_synced,
                "email_count": email_count,
                "calendar_event_count": event_count,
            }))
        }

        "sync" => {
            let token = state
                .google_auth
                .get_valid_token(db)
                .await?
                .ok_or_else(|| "Google not connected. Ask the user to connect first via Settings (Cmd+,).".to_string())?;

            let count = args["count"].as_u64().unwrap_or(50) as usize;

            let _ = app.emit("sync-status", json!({"status": "syncing", "step": "gmail"}));
            let gmail_result = google::gmail::sync_gmail(db, &token, count).await;
            let _ = app.emit("sync-status", json!({"status": "syncing", "step": "calendar"}));
            let calendar_result = google::calendar::sync_calendar(db, &token).await;
            let _ = app.emit("sync-status", json!({"status": "done"}));

            Ok(json!({
                "gmail": match gmail_result {
                    Ok(r) => json!({"synced": r.synced, "linked": r.linked, "errors": r.errors}),
                    Err(e) => json!({"error": e}),
                },
                "calendar": match calendar_result {
                    Ok(r) => json!({"synced": r.synced, "linked": r.linked, "errors": r.errors}),
                    Err(e) => json!({"error": e}),
                },
            }))
        }

        "sync_transcripts" => {
            let token = state
                .google_auth
                .get_valid_token(db)
                .await?
                .ok_or_else(|| "Google not connected. Ask the user to connect first via Settings (Cmd+,).".to_string())?;

            let _ = app.emit("sync-status", json!({"status": "syncing", "step": "transcripts"}));
            let result = google::transcripts::sync_transcripts(db, &token).await;
            let _ = app.emit("sync-status", json!({"status": "done"}));

            match result {
                Ok(r) => Ok(json!({
                    "found": r.found,
                    "imported": r.imported,
                    "skipped": r.skipped,
                    "errors": r.errors,
                    "transcripts": r.transcripts,
                })),
                Err(e) => Err(e),
            }
        }

        "connect" => {
            // Start the OAuth flow — this will open the browser
            let email = google::oauth::start_oauth_flow(db).await?;

            // Cache the token
            if let Ok(Some(token_data)) = google::oauth::load_token_file(&email) {
                if let Some(at) = token_data["access_token"].as_str() {
                    let expires_in = token_data["expires_in"].as_u64().unwrap_or(3600);
                    state
                        .google_auth
                        .set_access_token(at.to_string(), expires_in);

                    // Immediately sync (default 50 for initial connect)
                    let _ = app.emit("sync-status", json!({"status": "syncing", "step": "gmail"}));
                    let gmail_result = google::gmail::sync_gmail(db, at, 50).await;
                    let _ = app.emit("sync-status", json!({"status": "syncing", "step": "calendar"}));
                    let calendar_result = google::calendar::sync_calendar(db, at).await;
                    let _ = app.emit("sync-status", json!({"status": "done"}));

                    let _ = app.emit(
                        "google-connected",
                        json!({"connected": true, "email": &email}),
                    );

                    return Ok(json!({
                        "status": "connected",
                        "email": email,
                        "gmail": match gmail_result {
                            Ok(r) => json!({"synced": r.synced, "linked": r.linked}),
                            Err(e) => json!({"error": e}),
                        },
                        "calendar": match calendar_result {
                            Ok(r) => json!({"synced": r.synced, "linked": r.linked}),
                            Err(e) => json!({"error": e}),
                        },
                    }));
                }
            }

            let _ = app.emit(
                "google-connected",
                json!({"connected": true, "email": &email}),
            );

            Ok(json!({
                "status": "connected",
                "email": email,
                "note": "Connected but initial sync skipped — will sync on next auto-refresh."
            }))
        }

        _ => Err(format!("Unknown google action: {}", action)),
    }
}

fn build_system_prompt(db: &Arc<Database>) -> String {
    // Load user profile from DB
    let profile = db
        .query_json(
            "SELECT key, value FROM user_profile WHERE category IN ('identity', 'preferences')",
            &[],
        )
        .unwrap_or(json!([]));

    let mut name = "there".to_string();
    let mut style = "concise".to_string();
    if let Value::Array(ref rows) = profile {
        for row in rows {
            match row["key"].as_str() {
                Some("name") => name = row["value"].as_str().unwrap_or("there").to_string(),
                Some("communication_style") => {
                    style = row["value"].as_str().unwrap_or("concise").to_string()
                }
                _ => {}
            }
        }
    }

    // Check Google connection status
    let google_connected = crate::google::oauth::is_connected(db);
    let google_email = if google_connected {
        crate::google::oauth::load_primary_email(db)
            .ok()
            .flatten()
            .unwrap_or_default()
    } else {
        String::new()
    };

    // Check onboarding state
    let contact_count: i64 = db
        .query_json("SELECT COUNT(*) as count FROM contacts", &[])
        .and_then(|v| v[0]["count"].as_i64().ok_or_else(|| "no count".to_string()))
        .unwrap_or(0);

    let has_profile: bool = db
        .query_json(
            "SELECT COUNT(*) as count FROM user_profile WHERE category = 'identity'",
            &[],
        )
        .and_then(|v| {
            v[0]["count"]
                .as_i64()
                .map(|n| n > 0)
                .ok_or_else(|| "no count".to_string())
        })
        .unwrap_or(false);

    let onboarding_section = if !has_profile {
        r#"

## ONBOARDING MODE — First Run

This is a brand new user. Your FIRST message should be the welcome greeting:

```
        ╭──────────╮
        │  ◠    ◠  │
        │    ◡◡    │
        ╰────┬┬────╯
            ╱╲╱╲

  S O F T W A R E  of  Y O U
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Your personal data platform.
  Nice to meet you! ♡
```

Everything lives on your machine, and I'm your only interface.

I can track your relationships, log conversations, connect your email and calendar, make decisions, keep a journal — and I'll cross-reference all of it automatically.

After the greeting, ask: "First — what should I call you?"

Once they give their name, store it using the SQL tool, then ask about:
1. Their role (Freelancer/Consultant, Agency/Studio Owner, Solopreneur, Corporate/In-house)
2. What they're primarily tracking (Client relationships, Projects, Business communications, Personal network)
3. How you should communicate (Brief and direct, Detailed with context, Casual and conversational)

Store each answer in user_profile table using SQL:
INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('identity', 'name', '<name>', 'explicit', datetime('now'));
INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('identity', 'role', '<role>', 'explicit', datetime('now'));
INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('preferences', 'focus', '<focus>', 'explicit', datetime('now'));
INSERT OR REPLACE INTO user_profile (category, key, value, source, updated_at) VALUES ('preferences', 'communication_style', '<style>', 'explicit', datetime('now'));

After collecting preferences, transition: "Got it, [name]. Now let's get some data in here."

Then suggest adding contacts or importing a CSV. Only mention connecting Google if Google integration is available (check the App State section above).

After the user adds their first contact, show the dashboard panel to give them a sense of their workspace: [PANEL:dashboard]"#
    } else if contact_count == 0 {
        r#"

## Getting Started

The user has a profile but no contacts yet. Gently encourage them to add data:

**The best way to start is to give me data.** Suggest:
- "Add a contact named Sarah Chen, VP of Engineering at Acme"
- Drop a CSV of clients or contacts
- Paste a call transcript

Only suggest connecting Google if Google integration is available (check the App State section above).

Ask: "Who's someone you work with that you'd like to start tracking?""#
    } else {
        "" // Active user — no onboarding needed
    };

    // Build Google status section
    let google_section = if google_connected {
        format!(
            "- Google account connected ({google_email}). Gmail and Calendar sync is active.\n\
             - Sync fetches the 50 most recent emails and up to 100 calendar events (past 7 days + next 14 days). This takes about 30 seconds, not minutes.\n\
             - Data auto-refreshes every 15 minutes in the background. Never tell users sync takes more than a minute."
        )
    } else {
        "- Google account is NOT connected but IS available. The user can connect by saying \"connect Google\" or opening Settings (Cmd+,). When they connect, their browser will open for Google sign-in, and the connection completes automatically.\n\
         - Sync fetches the 50 most recent emails and up to 100 calendar events. It takes about 30 seconds.\n\
         - Do NOT invent sync durations. Never say sync takes \"15-20 minutes\" or similar — it takes seconds.".to_string()
    };

    format!(
        r#"You are Software of You — a personal data platform running as a native Mac app.
The user's name is {name}. Communication style preference: {style}.

## Your Interface — IMPORTANT

You are the ONLY interface. This is a chat-based app. There are NO menus, NO navigation bars, NO settings screens, NO "File > Preferences" menus. Everything happens through this conversation.

**What exists:**
- This chat window (where the user talks to you)
- A side panel that slides out when you include a [PANEL:...] marker (shows contact details, dashboards, etc.)
- A menu bar icon in the macOS status bar (shows nudges and quick input)
- Cmd+, keyboard shortcut opens a Settings panel in the side panel

**What does NOT exist — never reference these:**
- No "Settings menu" or "Settings page" in a menu bar
- No "Integrations" page
- No navigation or tabs
- No "Go to..." anything
- No buttons the user clicks to perform actions

**When the user wants to change settings:** Tell them to press Cmd+, or say "open settings" and you will show the settings panel.
**When the user wants to connect Google:** Use the `google` tool with action "connect". This opens their browser for sign-in and automatically syncs emails + calendar once connected.
**When the user asks about email/calendar and data seems stale or empty:** Use the `google` tool with action "sync" to trigger a fresh sync. Pass a `count` parameter to control how many emails to fetch (default 50). If the user asks for more emails (e.g. "get 300 emails"), just do it — pass count: 300. Don't argue or explain limits. Data auto-refreshes every 15 minutes, but you can sync on demand anytime.
**To check Google connection status:** Use the `google` tool with action "status" — it returns connection info, last sync times, and data counts.
**When the user wants to import meeting transcripts:** Use the `google` tool with action "sync_transcripts". This searches Gmail for Google Meet transcript notification emails (from gemini-notes@google.com), fetches the linked Google Docs content, and stores them in the database. Report the results: how many were found, imported, skipped (already imported), and any errors. If you get a 403 error about Google Docs access, tell the user to disconnect and reconnect Google in Settings (Cmd+,) to grant the updated permissions.

## App State
{google_section}
- Contacts in database: {contact_count}

## Core Behavior
- Be the interface. Users talk naturally. You translate to tool calls. Present results conversationally.
- Always cross-reference: when showing a contact, check linked projects/emails/meetings.
- Suggest next actions after completing a request.
- Never expose raw SQL or tool calls unless asked.
- Never fabricate data. If you can't derive a number, say so.
- NEVER reference UI elements that don't exist. You are a chat app with a side panel. That's it.

## Visual Panel — USE IT

This app has a side panel that shows rich visual content. You MUST include a panel marker whenever your response involves structured data. The panel is not optional decoration — it IS the interface for viewing data.

**Always open a panel for:**
- Any response about a specific contact → [PANEL:contact:<id>]
- Dashboard requests, status checks, "how am I doing" → [PANEL:dashboard]
- Calendar questions, schedule, "what's today look like" → [PANEL:calendar]
- Email discussions → [PANEL:email]
- Meeting prep or "who am I meeting with" → [PANEL:meeting-prep:<event_id>]
- Nudges, follow-ups, "what needs attention" → [PANEL:nudges]
- Commitments, action items → [PANEL:commitments]
- Settings requests, "open settings" → [PANEL:settings]

**Your text response should complement the panel**, not duplicate it. When a panel opens:
- Give a brief conversational summary in chat (2-3 sentences max)
- Let the panel show the details, stats, lists, and timelines
- Don't list out everything that's in the panel — the user can see it

**Example — BAD (no panel, text wall):**
"Sarah Chen is VP of Engineering at Acme. You last spoke 5 days ago. She has 3 open commitments..."

**Example — GOOD (panel + brief chat):**
"Here's Sarah's profile — you last connected 5 days ago and have 3 open items with her."
[PANEL:contact:42]

Place the marker at the END of your response, on its own line. Only include one panel hint per response.

## Style
- {style}. No filler.
- Use markdown tables for lists of 3+ items.
- Dates in human-readable format ("3 days ago", "next Tuesday").
- Focus on what matters — don't dump every field.{onboarding_section}"#
    )
}
