pub mod calendar;
pub mod gmail;
pub mod oauth;

use crate::db::Database;
use serde::{Deserialize, Serialize};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime};

/// In-memory Google auth state. Refresh tokens live in token files on disk;
/// the access token + expiry are ephemeral (lost on app restart, re-derived
/// from the refresh token on demand).
pub struct GoogleAuthState {
    inner: Mutex<GoogleAuthInner>,
}

struct GoogleAuthInner {
    access_token: Option<String>,
    expiry: Option<SystemTime>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GoogleStatus {
    pub connected: bool,
    pub email: Option<String>,
}

impl GoogleAuthState {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(GoogleAuthInner {
                access_token: None,
                expiry: None,
            }),
        }
    }

    /// Store a freshly obtained access token + its lifetime.
    pub fn set_access_token(&self, token: String, expires_in_secs: u64) {
        let mut inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
        inner.access_token = Some(token);
        inner.expiry = Some(SystemTime::now() + Duration::from_secs(expires_in_secs));
    }

    /// Get a valid access token, refreshing via the stored refresh token if expired.
    /// Returns `None` if no Google account is connected.
    ///
    /// Requires a reference to the database so we can look up the primary email
    /// and find the corresponding token file on disk.
    pub async fn get_valid_token(&self, db: &Arc<Database>) -> Result<Option<String>, String> {
        // Check if we have a non-expired token in memory.
        {
            let inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
            if let (Some(ref token), Some(expiry)) = (&inner.access_token, inner.expiry) {
                // Use a 60-second buffer so we refresh before actual expiry.
                if SystemTime::now() + Duration::from_secs(60) < expiry {
                    return Ok(Some(token.clone()));
                }
            }
        }

        // Look up the primary connected email from the database.
        let email = match oauth::load_primary_email(db)? {
            Some(e) => e,
            None => return Ok(None), // Not connected.
        };

        // Load the refresh token from the token file on disk.
        let refresh_token = match oauth::load_refresh_token_for(&email)? {
            Some(rt) => rt,
            None => return Ok(None), // Token file missing or corrupt.
        };

        let token_response = oauth::refresh_access_token(&refresh_token).await?;
        self.set_access_token(token_response.access_token.clone(), token_response.expires_in);

        Ok(Some(token_response.access_token))
    }

    /// Clear all in-memory auth state (used on disconnect).
    pub fn clear(&self) {
        let mut inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
        inner.access_token = None;
        inner.expiry = None;
    }
}
