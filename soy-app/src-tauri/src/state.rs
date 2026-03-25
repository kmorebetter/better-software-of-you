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
        let db = Database::new().expect("Failed to initialize database");
        let db_arc = Arc::new(db);

        // Load API key from the database (survives app rebuilds).
        let key = db_arc
            .query_json("SELECT value FROM soy_meta WHERE key = 'api_key'", &[])
            .ok()
            .and_then(|v| v.as_array()?.first()?.get("value")?.as_str().map(String::from));

        // One-time migration: if not in DB, check Keychain and migrate.
        let key = key.or_else(|| {
            let keychain_key = keyring::Entry::new("com.softwareofyou.app", "claude-api-key")
                .ok()
                .and_then(|e| e.get_password().ok())?;
            // Migrate to database for future launches
            let _ = db_arc.execute(
                "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES ('api_key', ?1, datetime('now'))",
                &[&keychain_key as &dyn rusqlite::ToSql],
            );
            Some(keychain_key)
        });

        Self {
            api_key: Mutex::new(key),
            db: db_arc,
            google_auth: GoogleAuthState::new(),
        }
    }
}
