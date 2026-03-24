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
