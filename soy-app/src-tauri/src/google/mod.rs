pub mod calendar;
pub mod gmail;
pub mod oauth;

use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::time::{Duration, SystemTime};

/// In-memory Google auth state. Refresh token lives in Keychain;
/// access token + expiry are ephemeral (lost on app restart, re-derived from refresh token).
pub struct GoogleAuthState {
    inner: Mutex<GoogleAuthInner>,
}

struct GoogleAuthInner {
    access_token: Option<String>,
    expiry: Option<SystemTime>,
    /// Held in memory during the PKCE flow between `connect_google` and `handle_google_callback`.
    pending_verifier: Option<String>,
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
                pending_verifier: None,
            }),
        }
    }

    /// Store the PKCE verifier while we wait for the callback.
    pub fn set_pending_verifier(&self, verifier: String) {
        let mut inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
        inner.pending_verifier = Some(verifier);
    }

    /// Take the pending verifier (consumes it).
    pub fn take_pending_verifier(&self) -> Option<String> {
        let mut inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
        inner.pending_verifier.take()
    }

    /// Store a freshly obtained access token + its lifetime.
    pub fn set_access_token(&self, token: String, expires_in_secs: u64) {
        let mut inner = self.inner.lock().expect("GoogleAuthState lock poisoned");
        inner.access_token = Some(token);
        inner.expiry = Some(SystemTime::now() + Duration::from_secs(expires_in_secs));
    }

    /// Get a valid access token, refreshing via the stored refresh token if expired.
    /// Returns `None` if no refresh token exists (user not connected).
    pub async fn get_valid_token(&self) -> Result<Option<String>, String> {
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

        // Try to refresh using the stored refresh token from Keychain.
        let refresh_token = Self::load_refresh_token()?;
        let refresh_token = match refresh_token {
            Some(rt) => rt,
            None => return Ok(None), // Not connected.
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
        inner.pending_verifier = None;
    }

    // -- Keychain helpers (refresh token + email) --

    const KEYCHAIN_SERVICE: &'static str = "com.softwareofyou.app";
    const KEYCHAIN_REFRESH: &'static str = "google-refresh-token";
    const KEYCHAIN_EMAIL: &'static str = "google-email";

    pub fn store_refresh_token(token: &str) -> Result<(), String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_REFRESH)
            .map_err(|e| format!("Keychain error: {}", e))?;
        entry
            .set_password(token)
            .map_err(|e| format!("Failed to save refresh token: {}", e))
    }

    pub fn load_refresh_token() -> Result<Option<String>, String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_REFRESH)
            .map_err(|e| format!("Keychain error: {}", e))?;
        match entry.get_password() {
            Ok(pw) => Ok(Some(pw)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(format!("Keychain read error: {}", e)),
        }
    }

    pub fn delete_refresh_token() -> Result<(), String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_REFRESH)
            .map_err(|e| format!("Keychain error: {}", e))?;
        match entry.delete_credential() {
            Ok(()) => Ok(()),
            Err(keyring::Error::NoEntry) => Ok(()), // Already gone, fine.
            Err(e) => Err(format!("Keychain delete error: {}", e)),
        }
    }

    pub fn store_email(email: &str) -> Result<(), String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_EMAIL)
            .map_err(|e| format!("Keychain error: {}", e))?;
        entry
            .set_password(email)
            .map_err(|e| format!("Failed to save email: {}", e))
    }

    pub fn load_email() -> Result<Option<String>, String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_EMAIL)
            .map_err(|e| format!("Keychain error: {}", e))?;
        match entry.get_password() {
            Ok(pw) => Ok(Some(pw)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(format!("Keychain read error: {}", e)),
        }
    }

    pub fn delete_email() -> Result<(), String> {
        let entry = keyring::Entry::new(Self::KEYCHAIN_SERVICE, Self::KEYCHAIN_EMAIL)
            .map_err(|e| format!("Keychain error: {}", e))?;
        match entry.delete_credential() {
            Ok(()) => Ok(()),
            Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(format!("Keychain delete error: {}", e)),
        }
    }
}
