use crate::db::Database;
use crate::tools;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};

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

            // Emit panel hint as a structured event (not visible text)
            if let Some(hint) = panel_hint {
                let _ = app.emit(
                    "chat-stream",
                    StreamEvent {
                        token: None,
                        done: None,
                        panel_hint: Some(hint),
                        error: None,
                    },
                );
            }

            let _ = app.emit(
                "chat-stream",
                StreamEvent {
                    token: None,
                    done: Some(true),
                    panel_hint: None,
                    error: None,
                },
            );
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
            let _ = app.emit(
                "chat-stream",
                StreamEvent {
                    token: Some(format!("*Using {}...*\n", tool_name)),
                    done: None,
                    panel_hint: None,
                    error: None,
                },
            );

            let result = tools::execute_tool(db, tool_name, tool_input);

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

After collecting preferences, transition: "Got it, [name]. Now let's get some data in here." Then suggest adding contacts, importing CSV, or connecting Google."#
    } else if contact_count == 0 {
        r#"

## Getting Started

The user has a profile but no contacts yet. Gently encourage them to add data:

**The best way to start is to give me data.** Suggest:
- "Add a contact named Sarah Chen, VP of Engineering at Acme"
- Drop a CSV of clients or contacts
- Paste a call transcript
- "Connect my Google account" to sync emails and calendar

Ask: "Who's someone you work with that you'd like to start tracking?""#
    } else {
        "" // Active user — no onboarding needed
    };

    format!(
        r#"You are Software of You — a personal data platform running as a native Mac app.
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
- Focus on what matters — don't dump every field.{onboarding_section}"#
    )
}
