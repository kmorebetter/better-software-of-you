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
