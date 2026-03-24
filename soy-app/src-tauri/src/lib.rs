mod claude;
mod commands;
mod db;
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
