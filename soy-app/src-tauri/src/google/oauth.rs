use crate::db::Database;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::path::PathBuf;
use std::sync::Arc;

// ---------------------------------------------------------------------------
// Configuration — embedded credentials (same as the Claude plugin)
// ---------------------------------------------------------------------------

const CLIENT_ID: &str = "50587301029-pb96imk0vvadpg8n5oa2q8ac1lfk5f9o.apps.googleusercontent.com";
const CLIENT_SECRET: &str = "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";
const REDIRECT_URI: &str = "http://localhost:8089";
const AUTH_ENDPOINT: &str = "https://accounts.google.com/o/oauth2/v2/auth";
const TOKEN_ENDPOINT: &str = "https://oauth2.googleapis.com/token";
const REVOKE_ENDPOINT: &str = "https://oauth2.googleapis.com/revoke";
const USERINFO_ENDPOINT: &str = "https://www.googleapis.com/oauth2/v2/userinfo";

const SCOPES: &str = "https://www.googleapis.com/auth/gmail.readonly \
                       https://www.googleapis.com/auth/calendar.readonly \
                       https://www.googleapis.com/auth/documents.readonly \
                       https://www.googleapis.com/auth/userinfo.email";

// ---------------------------------------------------------------------------
// PKCE helpers
// ---------------------------------------------------------------------------

/// Generate a cryptographically random code verifier (43-128 URL-safe chars).
/// We use 32 random bytes -> 43 base64url chars.
fn generate_code_verifier() -> String {
    use std::io::Read;
    let mut buf = [0u8; 32];
    let mut rng = std::fs::File::open("/dev/urandom").expect("Failed to open /dev/urandom");
    rng.read_exact(&mut buf).expect("Failed to read random bytes");
    base64url_encode(&buf)
}

/// Derive the S256 code challenge from a verifier:
///   challenge = BASE64URL(SHA256(verifier))
fn derive_code_challenge(verifier: &str) -> String {
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
// Token storage — file-based, compatible with the Claude plugin
// ---------------------------------------------------------------------------

/// Return the token storage directory: ~/.local/share/software-of-you/tokens/
pub fn token_dir() -> PathBuf {
    let data_home = dirs::data_dir().unwrap_or_else(|| PathBuf::from(".local/share"));
    data_home.join("software-of-you").join("tokens")
}

/// Convert an email to a safe filename: foo@bar.com -> foo_bar_com.json
fn email_to_filename(email: &str) -> String {
    email.replace('@', "_").replace('.', "_") + ".json"
}

/// Save tokens to a file in the token directory.
pub fn save_token_file(email: &str, tokens: &TokenResponse) -> Result<(), String> {
    let dir = token_dir();
    std::fs::create_dir_all(&dir).map_err(|e| format!("Failed to create token dir: {}", e))?;

    let path = dir.join(email_to_filename(email));
    let data = serde_json::json!({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in,
        "token_type": tokens.token_type,
        "saved_at": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
    });

    std::fs::write(&path, serde_json::to_string_pretty(&data).unwrap())
        .map_err(|e| format!("Failed to write token file: {}", e))
}

/// Load tokens from a file for the given email. Returns None if the file doesn't exist.
pub fn load_token_file(email: &str) -> Result<Option<serde_json::Value>, String> {
    let path = token_dir().join(email_to_filename(email));
    if !path.exists() {
        return Ok(None);
    }
    let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let data: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    Ok(Some(data))
}

/// Delete the token file for a given email.
pub fn delete_token_file(email: &str) -> Result<(), String> {
    let path = token_dir().join(email_to_filename(email));
    if path.exists() {
        std::fs::remove_file(&path).map_err(|e| format!("Failed to delete token file: {}", e))?;
    }
    Ok(())
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
async fn exchange_code(code: &str, verifier: &str) -> Result<TokenResponse, String> {
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
        // A 400 with "invalid_token" just means it was already revoked.
        if status.as_u16() == 400 && body.contains("invalid_token") {
            return Ok(());
        }
        return Err(format!("Revoke failed ({}): {}", status, body));
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Fetch user email
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct UserInfo {
    email: String,
}

/// Fetch the authenticated user's primary email address.
async fn fetch_user_email(access_token: &str) -> Result<String, String> {
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

// ---------------------------------------------------------------------------
// Localhost HTTP callback server
// ---------------------------------------------------------------------------

/// Wait for Google's OAuth callback on a temporary localhost HTTP server.
/// Accepts one connection, extracts the `code` query parameter, sends a
/// success page, and shuts down.
async fn wait_for_callback(listener: tokio::net::TcpListener) -> Result<String, String> {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};

    // Accept one connection with a 120-second timeout.
    let (mut stream, _) = tokio::time::timeout(
        std::time::Duration::from_secs(120),
        listener.accept(),
    )
    .await
    .map_err(|_| "OAuth timeout — no response from Google within 2 minutes".to_string())?
    .map_err(|e| format!("Accept error: {}", e))?;

    // Read the HTTP request.
    let mut buf = vec![0u8; 4096];
    let n = stream
        .read(&mut buf)
        .await
        .map_err(|e| format!("Read error: {}", e))?;
    let request = String::from_utf8_lossy(&buf[..n]);

    // Parse: GET /?code=...&scope=... HTTP/1.1
    let first_line = request.lines().next().unwrap_or("");
    let path = first_line.split_whitespace().nth(1).unwrap_or("");

    // Extract the code from the query string.
    let code = extract_query_param(path, "code").ok_or_else(|| {
        let error = extract_query_param(path, "error").unwrap_or_default();
        format!("OAuth denied: {}", error)
    })?;

    // Send a success response and close.
    let html = r#"<html><body style="font-family:system-ui;text-align:center;padding:60px">
        <h2 style="color:#18181b">Connected!</h2>
        <p style="color:#71717a">You can close this tab and return to Software of You.</p>
    </body></html>"#;
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        html.len(),
        html
    );
    stream.write_all(response.as_bytes()).await.ok();
    stream.flush().await.ok();

    Ok(code)
}

/// Extract a query parameter value from a URL path like `/?code=ABC&scope=xyz`.
fn extract_query_param(path: &str, key: &str) -> Option<String> {
    let query = path.split('?').nth(1)?;
    for param in query.split('&') {
        if let Some(value) = param.strip_prefix(&format!("{}=", key)) {
            return Some(urlencoding::decode(value).ok()?.into_owned());
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Database registration
// ---------------------------------------------------------------------------

/// Register (or update) a Google account in the `google_accounts` table.
fn register_account(db: &Arc<Database>, email: &str, display_name: Option<&str>) -> Result<(), String> {
    let label = email.split('@').nth(1).unwrap_or("unknown").to_string();
    let filename = email_to_filename(email);
    let display = display_name.unwrap_or("").to_string();

    db.execute(
        "INSERT INTO google_accounts (email, label, display_name, token_file, is_primary, connected_at, status)
         VALUES (?1, ?2, ?3, ?4,
            COALESCE((SELECT is_primary FROM google_accounts WHERE email = ?1),
                     CASE WHEN (SELECT COUNT(*) FROM google_accounts) = 0 THEN 1 ELSE 0 END),
            datetime('now'), 'active')
         ON CONFLICT(email) DO UPDATE SET
            token_file = excluded.token_file,
            status = 'active',
            connected_at = datetime('now')",
        &[
            &email as &dyn rusqlite::ToSql,
            &label,
            &display,
            &filename,
        ],
    )?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Main OAuth flow — synchronous localhost callback
// ---------------------------------------------------------------------------

/// Run the full Google OAuth flow:
///   1. Generate PKCE verifier + challenge
///   2. Start a temporary HTTP server on localhost:8089
///   3. Open the browser to the Google consent screen
///   4. Wait for the callback with the authorization code
///   5. Exchange code for tokens
///   6. Fetch the user's email
///   7. Save token file to disk
///   8. Register the account in the database
///
/// Returns the authenticated email address.
pub async fn start_oauth_flow(db: &Arc<Database>) -> Result<String, String> {
    // 1. Generate PKCE.
    let verifier = generate_code_verifier();
    let challenge = derive_code_challenge(&verifier);

    // 2. Start a temporary HTTP server on localhost:8089.
    let listener = tokio::net::TcpListener::bind("127.0.0.1:8089")
        .await
        .map_err(|e| format!("Failed to start callback server on port 8089: {}", e))?;

    // 3. Build the authorization URL.
    let auth_url = format!(
        "{}?client_id={}&redirect_uri={}&response_type=code&scope={}&\
         code_challenge={}&code_challenge_method=S256&access_type=offline&prompt=consent",
        AUTH_ENDPOINT,
        urlencoding::encode(CLIENT_ID),
        urlencoding::encode(REDIRECT_URI),
        urlencoding::encode(SCOPES),
        urlencoding::encode(&challenge),
    );

    // 4. Open the user's browser.
    open::that(&auth_url).map_err(|e| format!("Failed to open browser: {}", e))?;

    // 5. Wait for the callback.
    let code = wait_for_callback(listener).await?;

    // 6. Exchange the authorization code for tokens.
    let tokens = exchange_code(&code, &verifier).await?;

    // 7. Fetch the user's email.
    let email = fetch_user_email(&tokens.access_token).await?;

    // 8. Save token file to disk.
    save_token_file(&email, &tokens)?;

    // 9. Register in the google_accounts table.
    register_account(db, &email, None)?;

    Ok(email)
}

// ---------------------------------------------------------------------------
// Lookup helpers (for other modules)
// ---------------------------------------------------------------------------

/// Load the primary connected email from the database.
/// Returns None if no active accounts exist.
pub fn load_primary_email(db: &Arc<Database>) -> Result<Option<String>, String> {
    let rows = db.query_json(
        "SELECT email FROM google_accounts WHERE status = 'active' ORDER BY is_primary DESC LIMIT 1",
        &[],
    )?;
    if let Some(arr) = rows.as_array() {
        if let Some(first) = arr.first() {
            if let Some(email) = first["email"].as_str() {
                return Ok(Some(email.to_string()));
            }
        }
    }
    Ok(None)
}

/// Load the refresh token from the token file for the given email.
pub fn load_refresh_token_for(email: &str) -> Result<Option<String>, String> {
    match load_token_file(email)? {
        Some(data) => Ok(data["refresh_token"].as_str().map(String::from)),
        None => Ok(None),
    }
}

/// Check if any Google account is connected (has an active entry in the DB
/// and a token file on disk).
pub fn is_connected(db: &Arc<Database>) -> bool {
    load_primary_email(db)
        .ok()
        .flatten()
        .and_then(|email| load_token_file(&email).ok().flatten())
        .is_some()
}
