use crate::claude;
use crate::google;
use crate::state::AppState;
use crate::tools;
use tauri::{AppHandle, Emitter, State};

#[tauri::command]
pub async fn send_message(
    app: AppHandle,
    state: State<'_, AppState>,
    message: String,
    conversation_id: Option<i64>,
) -> Result<String, String> {
    let api_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?
        .clone()
        .ok_or_else(|| "No API key set. Please set your Claude API key first.".to_string())?;

    let db = state.db.clone();

    // Build message history from conversation
    let mut messages = Vec::new();

    if let Some(conv_id) = conversation_id {
        let history = db
            .query_json(
                "SELECT role, content, tool_calls FROM messages WHERE conversation_id = ?1 ORDER BY created_at ASC LIMIT 100",
                &[&conv_id as &dyn rusqlite::ToSql],
            )
            .unwrap_or(serde_json::json!([]));

        if let Some(rows) = history.as_array() {
            for row in rows {
                let role = row["role"].as_str().unwrap_or("user").to_string();
                let tool_calls = row["tool_calls"].as_str();

                // If tool_calls is set, this is a structured message (tool_use or tool_result).
                // Parse it back as JSON content for the Claude API.
                let content = if let Some(tc) = tool_calls {
                    serde_json::from_str::<serde_json::Value>(tc).unwrap_or_else(|_| {
                        serde_json::json!(row["content"].as_str().unwrap_or(""))
                    })
                } else {
                    // Plain text message
                    serde_json::json!(row["content"].as_str().unwrap_or(""))
                };

                messages.push(claude::ChatMessage { role, content });
            }
        }
    }

    // Add the new user message
    messages.push(claude::ChatMessage {
        role: "user".to_string(),
        content: serde_json::json!(message),
    });

    claude::send_with_tools(&app, &api_key, messages, &db, conversation_id).await?;
    Ok("done".to_string())
}

#[tauri::command]
pub async fn create_conversation(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let id = db.execute("INSERT INTO conversations (title) VALUES (NULL)", &[])?;
    Ok(serde_json::json!({ "id": id }))
}

#[tauri::command]
pub async fn get_recent_conversation(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let conversations = db
        .query_json(
            "SELECT id, title, created_at FROM conversations ORDER BY updated_at DESC LIMIT 1",
            &[],
        )
        .map_err(|e| e.to_string())?;

    if let Some(conv) = conversations.as_array().and_then(|a| a.first()) {
        let conv_id = conv["id"].as_i64().unwrap_or(0);
        let messages = db
            .query_json(
                "SELECT role, content, panel_hint, created_at FROM messages WHERE conversation_id = ?1 ORDER BY created_at ASC",
                &[&conv_id as &dyn rusqlite::ToSql],
            )
            .map_err(|e| e.to_string())?;

        Ok(serde_json::json!({
            "conversation": conv,
            "messages": messages,
        }))
    } else {
        Ok(serde_json::json!({ "conversation": null, "messages": [] }))
    }
}

#[tauri::command]
pub async fn save_message(
    state: State<'_, AppState>,
    conversation_id: i64,
    role: String,
    content: String,
    panel_hint: Option<String>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let id = db.execute(
        "INSERT INTO messages (conversation_id, role, content, panel_hint) VALUES (?1, ?2, ?3, ?4)",
        &[
            &conversation_id as &dyn rusqlite::ToSql,
            &role,
            &content,
            &panel_hint,
        ],
    )?;

    // Update conversation title from first user message
    if role == "user" {
        let title: String = if content.len() > 50 {
            content.chars().take(50).collect()
        } else {
            content.clone()
        };
        let _ = db.execute(
            "UPDATE conversations SET title = COALESCE(title, ?1), updated_at = datetime('now') WHERE id = ?2",
            &[&title as &dyn rusqlite::ToSql, &conversation_id],
        );
    } else {
        let _ = db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?1",
            &[&conversation_id as &dyn rusqlite::ToSql],
        );
    }

    Ok(serde_json::json!({ "id": id }))
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
    // Persist in the database (survives app rebuilds, no code-signing issues)
    let db = state.db.clone();
    db.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('api_key', ?1, datetime('now'))",
        &[&key as &dyn rusqlite::ToSql],
    )?;

    // Update in-memory state
    let mut api_key = state
        .api_key
        .lock()
        .map_err(|e| format!("Lock error: {}", e))?;
    *api_key = Some(key);

    Ok(())
}

#[tauri::command]
pub async fn get_panel_data(
    state: State<'_, AppState>,
    panel_type: String,
    entity_id: Option<i64>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    match panel_type.as_str() {
        "contact" => {
            let id = entity_id.ok_or("Contact panel requires entity_id")?;
            tools::profile::execute(&db, &serde_json::json!({"contact_id": id}))
        }
        "dashboard" => tools::overview::execute(&db),
        "nudges" => tools::intelligence::execute(&db, &serde_json::json!({"action": "nudges"})),
        "commitments" => {
            tools::intelligence::execute(&db, &serde_json::json!({"action": "commitments_view"}))
        }
        "calendar" => tools::calendar::execute(&db, &serde_json::json!({"action": "week"})),
        "email" => tools::email::execute(&db, &serde_json::json!({"action": "inbox"})),
        "meeting-prep" => {
            let id = entity_id.ok_or("Meeting prep requires event_id")?;
            tools::intelligence::execute(
                &db,
                &serde_json::json!({"action": "meeting_prep", "event_id": id}),
            )
        }
        _ => Err(format!("Unknown panel type: {}", panel_type)),
    }
}

#[tauri::command]
pub async fn get_onboarding_state(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();

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

    let stage = if !has_profile {
        "fresh"
    } else if contact_count == 0 {
        "has_profile"
    } else {
        "active"
    };

    Ok(serde_json::json!({
        "stage": stage,
        "contactCount": contact_count,
        "hasProfile": has_profile,
    }))
}

// ---------------------------------------------------------------------------
// Google OAuth commands
// ---------------------------------------------------------------------------

/// Start the Google OAuth flow: opens browser, waits for localhost callback,
/// exchanges code for tokens, saves to disk, registers in DB, then
/// immediately syncs Gmail + Calendar so data is available right away.
#[tauri::command]
pub async fn connect_google(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let email = google::oauth::start_oauth_flow(&db).await?;

    // Cache the access token in memory for this session.
    // (start_oauth_flow already saved it to disk; load it for the in-memory cache)
    let access_token = if let Ok(Some(token_data)) = google::oauth::load_token_file(&email) {
        if let Some(at) = token_data["access_token"].as_str() {
            let expires_in = token_data["expires_in"].as_u64().unwrap_or(3600);
            state
                .google_auth
                .set_access_token(at.to_string(), expires_in);
            Some(at.to_string())
        } else {
            None
        }
    } else {
        None
    };

    // Notify the frontend that Google is connected.
    let _ = app.emit(
        "google-connected",
        serde_json::json!({ "connected": true, "email": &email }),
    );

    // Immediately sync Gmail + Calendar so data is available without waiting
    // for the 15-minute auto-sync timer.
    let mut gmail_result = None;
    let mut calendar_result = None;

    if let Some(ref token) = access_token {
        let _ = app.emit(
            "sync-status",
            serde_json::json!({ "status": "syncing", "step": "gmail" }),
        );
        match google::gmail::sync_gmail(&db, token, 50).await {
            Ok(result) => gmail_result = Some(result),
            Err(e) => eprintln!("Initial gmail sync error: {}", e),
        }

        let _ = app.emit(
            "sync-status",
            serde_json::json!({ "status": "syncing", "step": "calendar" }),
        );
        match google::calendar::sync_calendar(&db, token).await {
            Ok(result) => calendar_result = Some(result),
            Err(e) => eprintln!("Initial calendar sync error: {}", e),
        }

        let _ = app.emit(
            "sync-status",
            serde_json::json!({ "status": "done" }),
        );
    }

    Ok(serde_json::json!({
        "status": "connected",
        "email": email,
        "gmail_sync": gmail_result,
        "calendar_sync": calendar_result,
    }))
}

/// Disconnect a Google account: revoke the token, remove files, update DB.
#[tauri::command]
pub async fn disconnect_google(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();

    // Find the primary connected email.
    let email = google::oauth::load_primary_email(&db)?;

    if let Some(ref email) = email {
        // Best-effort revoke at Google.
        if let Ok(Some(refresh_token)) = google::oauth::load_refresh_token_for(email) {
            if let Err(e) = google::oauth::revoke_token(&refresh_token).await {
                eprintln!(
                    "Warning: token revocation failed (continuing disconnect): {}",
                    e
                );
            }
        }

        // Delete the token file from disk.
        google::oauth::delete_token_file(email)?;

        // Mark as disconnected in the database.
        let _ = db.execute(
            "UPDATE google_accounts SET status = 'disconnected' WHERE email = ?1",
            &[email as &dyn rusqlite::ToSql],
        );
    }

    // Clear in-memory state.
    state.google_auth.clear();

    // Notify the frontend.
    let _ = app.emit(
        "google-connected",
        serde_json::json!({ "connected": false }),
    );

    Ok(serde_json::json!({
        "status": "disconnected",
        "message": "Google account disconnected."
    }))
}

/// Check whether a Google account is connected.
#[tauri::command]
pub async fn get_google_status(
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let db = state.db.clone();

    let accounts = db
        .query_json(
            "SELECT email, status, is_primary FROM google_accounts WHERE status = 'active' ORDER BY is_primary DESC",
            &[],
        )
        .unwrap_or(serde_json::json!([]));

    let connected = accounts
        .as_array()
        .map(|a| !a.is_empty())
        .unwrap_or(false);
    let primary_email = accounts
        .as_array()
        .and_then(|a| a.first())
        .and_then(|a| a["email"].as_str())
        .map(String::from);

    Ok(serde_json::json!({
        "connected": connected,
        "email": primary_email,
        "accounts": accounts,
    }))
}

// ---------------------------------------------------------------------------
// Gmail + Calendar sync commands
// ---------------------------------------------------------------------------

/// Sync recent Gmail messages into the local database.
#[tauri::command]
pub async fn sync_gmail(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let token = state
        .google_auth
        .get_valid_token(&db)
        .await?
        .ok_or_else(|| "Google not connected".to_string())?;
    let result = google::gmail::sync_gmail(&db, &token, 50).await?;
    Ok(serde_json::to_value(result).map_err(|e| format!("Serialize error: {}", e))?)
}

/// Sync calendar events into the local database.
#[tauri::command]
pub async fn sync_calendar(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let db = state.db.clone();
    let token = state
        .google_auth
        .get_valid_token(&db)
        .await?
        .ok_or_else(|| "Google not connected".to_string())?;
    let result = google::calendar::sync_calendar(&db, &token).await?;
    Ok(serde_json::to_value(result).map_err(|e| format!("Serialize error: {}", e))?)
}
