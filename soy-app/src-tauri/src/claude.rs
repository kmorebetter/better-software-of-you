use futures_util::StreamExt;
use reqwest::Client;
use serde::Serialize;
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

pub async fn stream_message(
    app: &AppHandle,
    api_key: &str,
    user_message: &str,
) -> Result<(), String> {
    let client = Client::new();

    let system_prompt = build_system_prompt();

    let request = json!({
        "model": MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
        "stream": true,
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
        let _ = app.emit("chat-stream", StreamEvent {
            token: None,
            done: None,
            panel_hint: None,
            error: Some(format!("API error {}: {}", status, body)),
        });
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
    // Phase 1: minimal system prompt. Will be expanded in Task 6 with tools + user profile.
    r#"You are Software of You — a personal data platform running as a native Mac app.
You help users manage their relationships, track conversations, and stay on top of commitments.
Be concise and direct. Use markdown for formatting. No filler.
When you don't have data to answer a question, say so honestly."#.to_string()
}
