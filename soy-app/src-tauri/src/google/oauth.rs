use serde::Deserialize;
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// Google OAuth client ID. Set via the `GOOGLE_CLIENT_ID` env var at compile time,
/// or falls back to a placeholder that must be replaced before real use.
const CLIENT_ID: &str = match option_env!("GOOGLE_CLIENT_ID") {
    Some(id) => id,
    None => "REPLACE_WITH_GOOGLE_CLIENT_ID",
};

/// For installed/desktop apps using PKCE, Google still requires a client_secret
/// (though it provides minimal security). Set via env var or placeholder.
const CLIENT_SECRET: &str = match option_env!("GOOGLE_CLIENT_SECRET") {
    Some(s) => s,
    None => "REPLACE_WITH_GOOGLE_CLIENT_SECRET",
};

const REDIRECT_URI: &str = "soy://auth/callback";
const AUTH_ENDPOINT: &str = "https://accounts.google.com/o/oauth2/v2/auth";
const TOKEN_ENDPOINT: &str = "https://oauth2.googleapis.com/token";
const REVOKE_ENDPOINT: &str = "https://oauth2.googleapis.com/revoke";
const USERINFO_ENDPOINT: &str = "https://www.googleapis.com/oauth2/v2/userinfo";

const SCOPES: &str = "https://www.googleapis.com/auth/gmail.readonly \
                       https://www.googleapis.com/auth/calendar.readonly \
                       https://www.googleapis.com/auth/userinfo.email";

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------

/// Generate a cryptographically random code verifier (43-128 URL-safe chars).
/// We use 32 random bytes -> 43 base64url chars.
pub fn generate_code_verifier() -> String {
    use std::io::Read;
    let mut buf = [0u8; 32];
    // Use /dev/urandom on macOS (always available, non-blocking).
    let mut rng = std::fs::File::open("/dev/urandom").expect("Failed to open /dev/urandom");
    rng.read_exact(&mut buf).expect("Failed to read random bytes");
    base64url_encode(&buf)
}

/// Derive the S256 code challenge from a verifier:
///   challenge = BASE64URL(SHA256(verifier))
pub fn derive_code_challenge(verifier: &str) -> String {
    let hash = Sha256::digest(verifier.as_bytes());
    base64url_encode(&hash)
}

/// Base64-URL encode without padding (per RFC 7636).
fn base64url_encode(data: &[u8]) -> String {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;
    URL_SAFE_NO_PAD.encode(data)
}

// ---------------------------------------------------------------------------
// OAuth URL builder
// ---------------------------------------------------------------------------

/// Build the full Google authorization URL the user's browser should open.
/// Returns `(url, code_verifier)` — the verifier must be stored until the callback.
pub fn build_auth_url() -> (String, String) {
    let verifier = generate_code_verifier();
    let challenge = derive_code_challenge(&verifier);

    let url = format!(
        "{}?client_id={}&redirect_uri={}&response_type=code&scope={}&\
         code_challenge={}&code_challenge_method=S256&access_type=offline&prompt=consent",
        AUTH_ENDPOINT,
        urlencoding::encode(CLIENT_ID),
        urlencoding::encode(REDIRECT_URI),
        urlencoding::encode(SCOPES),
        urlencoding::encode(&challenge),
    );

    (url, verifier)
}

// ---------------------------------------------------------------------------
// Token exchange / refresh
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
pub struct TokenResponse {
    pub access_token: String,
    pub expires_in: u64,
    pub refresh_token: Option<String>,
    pub token_type: String,
}

/// Exchange the authorization code (+ PKCE verifier) for tokens.
pub async fn exchange_code(code: &str, verifier: &str) -> Result<TokenResponse, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(TOKEN_ENDPOINT)
        .form(&[
            ("code", code),
            ("client_id", CLIENT_ID),
            ("client_secret", CLIENT_SECRET),
            ("redirect_uri", REDIRECT_URI),
            ("grant_type", "authorization_code"),
            ("code_verifier", verifier),
        ])
        .send()
        .await
        .map_err(|e| format!("Token exchange request failed: {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp
            .text()
            .await
            .unwrap_or_else(|_| "unable to read body".into());
        return Err(format!(
            "Token exchange failed ({}): {}",
            status, body
        ));
    }

    resp.json::<TokenResponse>()
        .await
        .map_err(|e| format!("Failed to parse token response: {}", e))
}

/// Use a refresh token to obtain a new access token.
pub async fn refresh_access_token(refresh_token: &str) -> Result<TokenResponse, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(TOKEN_ENDPOINT)
        .form(&[
            ("refresh_token", refresh_token),
            ("client_id", CLIENT_ID),
            ("client_secret", CLIENT_SECRET),
            ("grant_type", "refresh_token"),
        ])
        .send()
        .await
        .map_err(|e| format!("Token refresh request failed: {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp
            .text()
            .await
            .unwrap_or_else(|_| "unable to read body".into());
        return Err(format!(
            "Token refresh failed ({}): {}",
            status, body
        ));
    }

    resp.json::<TokenResponse>()
        .await
        .map_err(|e| format!("Failed to parse refresh response: {}", e))
}

// ---------------------------------------------------------------------------
// Revocation
// ---------------------------------------------------------------------------

/// Revoke a token (access or refresh) at Google's endpoint.
pub async fn revoke_token(token: &str) -> Result<(), String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(REVOKE_ENDPOINT)
        .form(&[("token", token)])
        .send()
        .await
        .map_err(|e| format!("Revoke request failed: {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp
            .text()
            .await
            .unwrap_or_else(|_| "unable to read body".into());
        // A 400 with "invalid_token" just means it was already revoked. Not an error.
        if status.as_u16() == 400 && body.contains("invalid_token") {
            return Ok(());
        }
        return Err(format!("Revoke failed ({}): {}", status, body));
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Fetch user email (for display in connection status)
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct UserInfo {
    email: String,
}

/// Fetch the authenticated user's primary email address.
pub async fn fetch_user_email(access_token: &str) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .get(USERINFO_ENDPOINT)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| format!("UserInfo request failed: {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp
            .text()
            .await
            .unwrap_or_else(|_| "unable to read body".into());
        return Err(format!("UserInfo failed ({}): {}", status, body));
    }

    let info: UserInfo = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse UserInfo: {}", e))?;
    Ok(info.email)
}
