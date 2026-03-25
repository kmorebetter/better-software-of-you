use crate::db::Database;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

// ---------------------------------------------------------------------------
// Gmail API response types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct MessageList {
    messages: Option<Vec<MessageRef>>,
}

#[derive(Debug, Deserialize)]
struct MessageRef {
    id: String,
}

#[derive(Debug, Deserialize)]
struct Message {
    id: String,
    #[serde(rename = "threadId")]
    thread_id: Option<String>,
    #[serde(rename = "labelIds")]
    label_ids: Option<Vec<String>>,
    snippet: Option<String>,
    payload: Option<MessagePayload>,
}

#[derive(Debug, Deserialize)]
struct MessagePayload {
    headers: Option<Vec<Header>>,
}

#[derive(Debug, Clone, Deserialize)]
struct Header {
    name: String,
    value: String,
}

// ---------------------------------------------------------------------------
// Sync result
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
pub struct SyncResult {
    pub synced: usize,
    pub linked: usize,
    pub errors: usize,
}

// ---------------------------------------------------------------------------
// Core sync logic
// ---------------------------------------------------------------------------

/// Fetch recent Gmail messages and upsert into the local database.
///
/// `user_email` is the authenticated Google account email, used to determine
/// inbound vs outbound direction. If not available, all messages default to inbound.
pub async fn sync_gmail(
    db: &Arc<Database>,
    access_token: &str,
) -> Result<SyncResult, String> {
    let client = reqwest::Client::new();

    // Resolve the user's own email for direction logic.
    let user_email = super::GoogleAuthState::load_email()?
        .unwrap_or_default()
        .to_lowercase();

    // 1. Fetch the list of recent message IDs.
    let list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=50";
    let list_resp = client
        .get(list_url)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| format!("Gmail list request failed: {}", e))?;

    if !list_resp.status().is_success() {
        let status = list_resp.status();
        let body = list_resp.text().await.unwrap_or_default();
        return Err(format!("Gmail list failed ({}): {}", status, body));
    }

    let list: MessageList = list_resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse message list: {}", e))?;

    let message_refs = match list.messages {
        Some(msgs) => msgs,
        None => {
            // No messages at all — still update the timestamp.
            update_sync_timestamp(db)?;
            return Ok(SyncResult {
                synced: 0,
                linked: 0,
                errors: 0,
            });
        }
    };

    // 2. Fetch metadata for each message and upsert.
    let mut synced: usize = 0;
    let mut linked: usize = 0;
    let mut errors: usize = 0;

    for msg_ref in &message_refs {
        let detail_url = format!(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/{}?\
             format=metadata\
             &metadataHeaders=From\
             &metadataHeaders=To\
             &metadataHeaders=Subject\
             &metadataHeaders=Date",
            msg_ref.id
        );

        let detail_resp = match client
            .get(&detail_url)
            .bearer_auth(access_token)
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Gmail fetch error for {}: {}", msg_ref.id, e);
                errors += 1;
                continue;
            }
        };

        if !detail_resp.status().is_success() {
            errors += 1;
            continue;
        }

        let message: Message = match detail_resp.json().await {
            Ok(m) => m,
            Err(e) => {
                eprintln!("Gmail parse error for {}: {}", msg_ref.id, e);
                errors += 1;
                continue;
            }
        };

        // 3. Extract headers.
        let headers = message
            .payload
            .as_ref()
            .and_then(|p| p.headers.as_ref())
            .cloned()
            .unwrap_or_default();

        let from_raw = header_value(&headers, "From").unwrap_or_default();
        let to_raw = header_value(&headers, "To").unwrap_or_default();
        let subject = header_value(&headers, "Subject").unwrap_or_default();
        let date = header_value(&headers, "Date").unwrap_or_default();

        let (from_name, from_email) = parse_email_address(&from_raw);
        let snippet = message.snippet.clone().unwrap_or_default();

        // 4. Determine direction.
        let direction = if from_email.to_lowercase() == user_email {
            "outbound"
        } else {
            "inbound"
        };

        // 5. Determine if read (no UNREAD label).
        let is_read: i32 = match &message.label_ids {
            Some(labels) => {
                if labels.iter().any(|l| l == "UNREAD") {
                    0
                } else {
                    1
                }
            }
            None => 1,
        };

        // 6. Try to match a contact by email address.
        //    For inbound: match from_email. For outbound: match to_addresses.
        let match_email = if direction == "inbound" {
            from_email.clone()
        } else {
            // For outbound, try the first To address.
            let (_, to_email) = parse_email_address(&to_raw);
            to_email
        };

        let contact_id = find_contact_by_email(db, &match_email)?;
        if contact_id.is_some() {
            linked += 1;
        }

        // 7. Upsert into emails table.
        //    Columns: gmail_id, thread_id, contact_id, direction, from_address,
        //    to_addresses, subject, snippet, body_preview, labels, is_read,
        //    is_starred, received_at, synced_at, from_name
        let labels_json = message
            .label_ids
            .as_ref()
            .map(|l| serde_json::to_string(l).unwrap_or_default());

        let is_starred: i32 = message
            .label_ids
            .as_ref()
            .map(|labels| {
                if labels.iter().any(|l| l == "STARRED") {
                    1
                } else {
                    0
                }
            })
            .unwrap_or(0);

        db.execute(
            "INSERT OR REPLACE INTO emails (
                gmail_id, thread_id, contact_id, direction, from_address,
                to_addresses, subject, snippet, body_preview, labels,
                is_read, is_starred, received_at, synced_at, from_name
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, datetime('now'), ?14)",
            &[
                &message.id as &dyn rusqlite::ToSql,
                &message.thread_id,
                &contact_id,
                &direction,
                &from_email,
                &to_raw,
                &subject,
                &snippet,
                &snippet, // body_preview = snippet for metadata-only fetch
                &labels_json,
                &is_read,
                &is_starred,
                &date,
                &from_name,
            ],
        )?;

        synced += 1;
    }

    // 8. Update the sync timestamp.
    update_sync_timestamp(db)?;

    Ok(SyncResult {
        synced,
        linked,
        errors,
    })
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn header_value(headers: &[Header], name: &str) -> Option<String> {
    headers
        .iter()
        .find(|h| h.name.eq_ignore_ascii_case(name))
        .map(|h| h.value.clone())
}

/// Parse "Display Name <email@example.com>" into (name, email).
/// Falls back to (raw, raw) if no angle brackets are found.
fn parse_email_address(raw: &str) -> (String, String) {
    if let Some(start) = raw.find('<') {
        if let Some(end) = raw.find('>') {
            let name = raw[..start].trim().trim_matches('"').to_string();
            let email = raw[start + 1..end].trim().to_string();
            return (name, email);
        }
    }
    // Bare email address.
    (String::new(), raw.trim().to_string())
}

fn find_contact_by_email(db: &Arc<Database>, email: &str) -> Result<Option<i64>, String> {
    if email.is_empty() {
        return Ok(None);
    }
    let rows = db.query_json(
        "SELECT id FROM contacts WHERE LOWER(email) = LOWER(?1) LIMIT 1",
        &[&email as &dyn rusqlite::ToSql],
    )?;
    if let Some(arr) = rows.as_array() {
        if let Some(first) = arr.first() {
            if let Some(id) = first.get("id").and_then(|v| v.as_i64()) {
                return Ok(Some(id));
            }
        }
    }
    Ok(None)
}

fn update_sync_timestamp(db: &Arc<Database>) -> Result<(), String> {
    db.execute(
        "INSERT OR REPLACE INTO soy_meta (key, value, updated_at) \
         VALUES ('gmail_last_synced', datetime('now'), datetime('now'))",
        &[],
    )?;
    Ok(())
}
