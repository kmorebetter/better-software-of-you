use crate::claude;
use crate::state::AppState;
use crate::tools;
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
