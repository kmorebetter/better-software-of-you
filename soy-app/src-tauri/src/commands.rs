use crate::claude;
use crate::google::{self, GoogleAuthState};
use crate::state::AppState;
use crate::tools;
use tauri::{AppHandle, Emitter, State};

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

/// Start the Google OAuth flow: generate PKCE, open browser to consent screen.
#[tauri::command]
pub async fn connect_google(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let (url, verifier) = google::oauth::build_auth_url();

    // Store the verifier so we can use it when the callback arrives.
    state.google_auth.set_pending_verifier(verifier);

    // Open the authorization URL in the user's default browser.
    open::that(&url).map_err(|e| format!("Failed to open browser: {}", e))?;

    Ok(serde_json::json!({
        "status": "pending",
        "message": "Browser opened for Google sign-in. Waiting for authorization..."
    }))
}

/// Handle the OAuth callback — exchange the authorization code for tokens.
/// Called from the deep-link handler (not directly by frontend).
#[tauri::command]
pub async fn handle_google_callback(
    app: AppHandle,
    state: State<'_, AppState>,
    code: String,
) -> Result<serde_json::Value, String> {
    let verifier = state
        .google_auth
        .take_pending_verifier()
        .ok_or_else(|| "No pending OAuth flow. Please start connection again.".to_string())?;

    // Exchange code for tokens.
    let token_response = google::oauth::exchange_code(&code, &verifier).await?;

    // Store refresh token in Keychain (persistent across restarts).
    if let Some(ref refresh_token) = token_response.refresh_token {
        GoogleAuthState::store_refresh_token(refresh_token)?;
    }

    // Store access token in memory.
    state
        .google_auth
        .set_access_token(token_response.access_token.clone(), token_response.expires_in);

    // Fetch and store the user's email for display purposes.
    match google::oauth::fetch_user_email(&token_response.access_token).await {
        Ok(email) => {
            GoogleAuthState::store_email(&email)?;
        }
        Err(e) => {
            // Non-fatal: we still have valid tokens even if email fetch fails.
            eprintln!("Warning: could not fetch Google user email: {}", e);
        }
    }

    // Notify the frontend.
    let _ = app.emit("google-connected", serde_json::json!({ "connected": true }));

    Ok(serde_json::json!({
        "status": "connected",
        "message": "Google account connected successfully."
    }))
}

/// Disconnect the Google account: revoke the token, remove from Keychain, clear memory.
#[tauri::command]
pub async fn disconnect_google(
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    // Best-effort revoke at Google (don't fail if network is down).
    if let Ok(Some(refresh_token)) = GoogleAuthState::load_refresh_token() {
        if let Err(e) = google::oauth::revoke_token(&refresh_token).await {
            eprintln!("Warning: token revocation failed (continuing disconnect): {}", e);
        }
    }

    // Remove from Keychain.
    GoogleAuthState::delete_refresh_token()?;
    GoogleAuthState::delete_email()?;

    // Clear in-memory state.
    state.google_auth.clear();

    // Notify the frontend.
    let _ = app.emit("google-connected", serde_json::json!({ "connected": false }));

    Ok(serde_json::json!({
        "status": "disconnected",
        "message": "Google account disconnected."
    }))
}

/// Check whether a Google account is connected (has a valid refresh token in Keychain).
#[tauri::command]
pub async fn get_google_status() -> Result<serde_json::Value, String> {
    let connected = GoogleAuthState::load_refresh_token()?.is_some();
    let email = GoogleAuthState::load_email()?;

    Ok(serde_json::json!({
        "connected": connected,
        "email": email
    }))
}

// ---------------------------------------------------------------------------
// Gmail + Calendar sync commands
// ---------------------------------------------------------------------------

/// Sync recent Gmail messages into the local database.
#[tauri::command]
pub async fn sync_gmail(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let token = state
        .google_auth
        .get_valid_token()
        .await?
        .ok_or_else(|| "Google not connected".to_string())?;
    let db = state.db.clone();
    let result = google::gmail::sync_gmail(&db, &token).await?;
    Ok(serde_json::to_value(result).map_err(|e| format!("Serialize error: {}", e))?)
}

/// Sync calendar events into the local database.
#[tauri::command]
pub async fn sync_calendar(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let token = state
        .google_auth
        .get_valid_token()
        .await?
        .ok_or_else(|| "Google not connected".to_string())?;
    let db = state.db.clone();
    let result = google::calendar::sync_calendar(&db, &token).await?;
    Ok(serde_json::to_value(result).map_err(|e| format!("Serialize error: {}", e))?)
}
