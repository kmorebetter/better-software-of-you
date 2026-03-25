use crate::db::Database;
use crate::google::GoogleAuthState;
use std::sync::{Arc, Mutex};

pub struct AppState {
    pub api_key: Mutex<Option<String>>,
    pub db: Arc<Database>,
    pub google_auth: GoogleAuthState,
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
            google_auth: GoogleAuthState::new(),
        }
    }
}
