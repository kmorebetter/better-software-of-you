use crate::db::Database;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct GmailMessageList {
    messages: Option<Vec<GmailMessageRef>>,
}

#[derive(Debug, Deserialize)]
struct GmailMessageRef {
    id: String,
}

#[derive(Debug, Deserialize)]
struct GmailMessage {
    id: String,
    payload: Option<GmailPayload>,
    #[serde(rename = "internalDate")]
    internal_date: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GmailPayload {
    headers: Option<Vec<GmailHeader>>,
    body: Option<GmailBody>,
    parts: Option<Vec<GmailPart>>,
}

#[derive(Debug, Deserialize)]
struct GmailHeader {
    name: String,
    value: String,
}

#[derive(Debug, Deserialize)]
struct GmailBody {
    data: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GmailPart {
    #[serde(rename = "mimeType")]
    mime_type: Option<String>,
    body: Option<GmailBody>,
    parts: Option<Vec<GmailPart>>,
}

/// Google Docs API response
#[derive(Debug, Deserialize)]
struct GoogleDoc {
    title: Option<String>,
    body: Option<DocBody>,
}

#[derive(Debug, Deserialize)]
struct DocBody {
    content: Option<Vec<DocContent>>,
}

#[derive(Debug, Deserialize)]
struct DocContent {
    paragraph: Option<DocParagraph>,
}

#[derive(Debug, Deserialize)]
struct DocParagraph {
    elements: Option<Vec<DocElement>>,
}

#[derive(Debug, Deserialize)]
struct DocElement {
    #[serde(rename = "textRun")]
    text_run: Option<DocTextRun>,
}

#[derive(Debug, Deserialize)]
struct DocTextRun {
    content: Option<String>,
}

// ---------------------------------------------------------------------------
// Result
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
pub struct TranscriptSyncResult {
    pub found: usize,
    pub imported: usize,
    pub skipped: usize,
    pub errors: usize,
    pub transcripts: Vec<ImportedTranscript>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ImportedTranscript {
    pub title: String,
    pub doc_id: String,
    pub word_count: usize,
}

// ---------------------------------------------------------------------------
// Core sync logic
// ---------------------------------------------------------------------------

/// Search Gmail for Google Meet transcript notification emails, fetch the
/// linked Google Docs content, and store as transcripts in the database.
pub async fn sync_transcripts(
    db: &Arc<Database>,
    access_token: &str,
) -> Result<TranscriptSyncResult, String> {
    let client = reqwest::Client::new();
    let mut result = TranscriptSyncResult {
        found: 0,
        imported: 0,
        skipped: 0,
        errors: 0,
        transcripts: Vec::new(),
    };

    // 1. Search Gmail for transcript notification emails from Google.
    let search_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages\
        ?q=from%3Agemini-notes%40google.com&maxResults=25";
    let list_resp = client
        .get(search_url)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| format!("Gmail search failed: {}", e))?;

    if !list_resp.status().is_success() {
        let status = list_resp.status();
        let body = list_resp.text().await.unwrap_or_default();
        return Err(format!("Gmail search failed ({}): {}", status, body));
    }

    let list: GmailMessageList = list_resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse message list: {}", e))?;

    let message_refs = match list.messages {
        Some(msgs) => msgs,
        None => return Ok(result), // No transcript emails found
    };

    result.found = message_refs.len();

    // 2. For each email, fetch full content and extract Google Docs link.
    for msg_ref in &message_refs {
        // Check if we already imported this email.
        let already_imported = db
            .query_json(
                "SELECT COUNT(*) as count FROM transcript_sources WHERE email_id = ?1",
                &[&msg_ref.id as &dyn rusqlite::ToSql],
            )
            .and_then(|v| v[0]["count"].as_i64().ok_or_else(|| "no count".into()))
            .unwrap_or(0);

        if already_imported > 0 {
            result.skipped += 1;
            continue;
        }

        // Fetch the full email message.
        let detail_url = format!(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/{}?format=full",
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
                eprintln!("Transcript email fetch error for {}: {}", msg_ref.id, e);
                result.errors += 1;
                continue;
            }
        };

        if !detail_resp.status().is_success() {
            result.errors += 1;
            continue;
        }

        let message: GmailMessage = match detail_resp.json().await {
            Ok(m) => m,
            Err(e) => {
                eprintln!("Transcript parse error for {}: {}", msg_ref.id, e);
                result.errors += 1;
                continue;
            }
        };

        // Extract subject and body text.
        let subject = message
            .payload
            .as_ref()
            .and_then(|p| p.headers.as_ref())
            .and_then(|headers| {
                headers
                    .iter()
                    .find(|h| h.name.eq_ignore_ascii_case("Subject"))
                    .map(|h| h.value.clone())
            })
            .unwrap_or_default();

        let body_text = extract_body_text(&message);

        // Find the Google Docs link in the email body.
        let doc_id = match extract_doc_id(&body_text) {
            Some(id) => id,
            None => {
                eprintln!("No Google Docs link found in transcript email {}", msg_ref.id);
                result.errors += 1;
                continue;
            }
        };

        // 3. Fetch the Google Doc content.
        let doc_url = format!(
            "https://docs.googleapis.com/v1/documents/{}",
            doc_id
        );
        let doc_resp = match client
            .get(&doc_url)
            .bearer_auth(access_token)
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => {
                eprintln!("Google Docs fetch error for {}: {}", doc_id, e);
                result.errors += 1;
                continue;
            }
        };

        if !doc_resp.status().is_success() {
            let status = doc_resp.status();
            if status.as_u16() == 403 {
                return Err("Google Docs access denied. You may need to reconnect Google \
                    with updated permissions: open Settings (Cmd+,), disconnect, and reconnect."
                    .to_string());
            }
            eprintln!("Google Docs error ({}): doc {}", status, doc_id);
            result.errors += 1;
            continue;
        }

        let doc: GoogleDoc = match doc_resp.json().await {
            Ok(d) => d,
            Err(e) => {
                eprintln!("Google Docs parse error for {}: {}", doc_id, e);
                result.errors += 1;
                continue;
            }
        };

        // 4. Extract plain text from the document.
        let doc_title = doc.title.clone().unwrap_or_else(|| subject.clone());
        let raw_text = extract_doc_text(&doc);

        if raw_text.trim().is_empty() {
            eprintln!("Empty transcript content for doc {}", doc_id);
            result.skipped += 1;
            continue;
        }

        let word_count = raw_text.split_whitespace().count();

        // 5. Parse occurred_at from email timestamp.
        let occurred_at = message
            .internal_date
            .as_ref()
            .and_then(|ms| ms.parse::<i64>().ok())
            .map(|ms| {
                let secs = ms / 1000;
                chrono::DateTime::from_timestamp(secs, 0)
                    .map(|dt| dt.format("%Y-%m-%d %H:%M:%S").to_string())
            })
            .flatten()
            .unwrap_or_else(|| chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string());

        // 6. Store the transcript.
        let transcript_id = db.execute(
            "INSERT INTO transcripts (title, source, raw_text, occurred_at, source_email_id, source_doc_id)
             VALUES (?1, 'google_meet', ?2, ?3, ?4, ?5)",
            &[
                &doc_title as &dyn rusqlite::ToSql,
                &raw_text,
                &occurred_at,
                &msg_ref.id,
                &doc_id,
            ],
        )?;

        // 7. Record the source for deduplication.
        let doc_url_str = format!("https://docs.google.com/document/d/{}", doc_id);
        let _ = db.execute(
            "INSERT OR IGNORE INTO transcript_sources (transcript_id, email_id, doc_id, doc_url, source_type, fetched_at)
             VALUES (?1, ?2, ?3, ?4, 'google_meet', datetime('now'))",
            &[
                &transcript_id as &dyn rusqlite::ToSql,
                &msg_ref.id,
                &doc_id,
                &doc_url_str,
            ],
        );

        // 8. Try to match to a calendar event (within ±30 min of transcript time).
        let _ = db.execute(
            "UPDATE transcripts SET source_calendar_event_id = (
                SELECT id FROM calendar_events
                WHERE ABS(strftime('%s', start_time) - strftime('%s', ?1)) < 1800
                ORDER BY ABS(strftime('%s', start_time) - strftime('%s', ?1)) ASC
                LIMIT 1
             ) WHERE id = ?2",
            &[&occurred_at as &dyn rusqlite::ToSql, &transcript_id],
        );

        // 9. Log the import.
        let _ = db.execute(
            "INSERT INTO activity_log (entity_type, entity_id, action, details, created_at)
             VALUES ('transcript', ?1, 'imported', ?2, datetime('now'))",
            &[
                &transcript_id as &dyn rusqlite::ToSql,
                &format!("Imported: {} ({} words)", doc_title, word_count),
            ],
        );

        result.imported += 1;
        result.transcripts.push(ImportedTranscript {
            title: doc_title,
            doc_id,
            word_count,
        });
    }

    Ok(result)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Recursively extract the plain text body from a Gmail message.
fn extract_body_text(message: &GmailMessage) -> String {
    let payload = match &message.payload {
        Some(p) => p,
        None => return String::new(),
    };

    // Try direct body first (simple messages).
    if let Some(body) = &payload.body {
        if let Some(data) = &body.data {
            if let Ok(decoded) = base64url_decode(data) {
                return decoded;
            }
        }
    }

    // Walk multipart parts looking for text/plain or text/html.
    if let Some(parts) = &payload.parts {
        return extract_text_from_parts(parts);
    }

    String::new()
}

fn extract_text_from_parts(parts: &[GmailPart]) -> String {
    // Prefer text/plain.
    for part in parts {
        if part.mime_type.as_deref() == Some("text/plain") {
            if let Some(body) = &part.body {
                if let Some(data) = &body.data {
                    if let Ok(decoded) = base64url_decode(data) {
                        return decoded;
                    }
                }
            }
        }
        // Recurse into nested parts.
        if let Some(sub_parts) = &part.parts {
            let text = extract_text_from_parts(sub_parts);
            if !text.is_empty() {
                return text;
            }
        }
    }

    // Fall back to text/html.
    for part in parts {
        if part.mime_type.as_deref() == Some("text/html") {
            if let Some(body) = &part.body {
                if let Some(data) = &body.data {
                    if let Ok(decoded) = base64url_decode(data) {
                        return decoded;
                    }
                }
            }
        }
    }

    String::new()
}

/// Decode base64url-encoded data (used by Gmail API).
fn base64url_decode(data: &str) -> Result<String, String> {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine;

    let bytes = URL_SAFE_NO_PAD
        .decode(data.trim())
        .map_err(|e| format!("base64 decode error: {}", e))?;
    String::from_utf8(bytes).map_err(|e| format!("UTF-8 decode error: {}", e))
}

/// Extract a Google Docs document ID from text containing a Docs URL.
fn extract_doc_id(text: &str) -> Option<String> {
    // Match: https://docs.google.com/document/d/{DOC_ID}/...
    let marker = "docs.google.com/document/d/";
    let start = text.find(marker)? + marker.len();
    let rest = &text[start..];
    let end = rest
        .find(|c: char| !c.is_alphanumeric() && c != '-' && c != '_')
        .unwrap_or(rest.len());
    let doc_id = &rest[..end];
    if doc_id.is_empty() {
        None
    } else {
        Some(doc_id.to_string())
    }
}

/// Walk a Google Docs document body and extract all text runs as plain text.
fn extract_doc_text(doc: &GoogleDoc) -> String {
    let mut text = String::new();
    if let Some(body) = &doc.body {
        if let Some(content) = &body.content {
            for block in content {
                if let Some(para) = &block.paragraph {
                    if let Some(elements) = &para.elements {
                        for elem in elements {
                            if let Some(run) = &elem.text_run {
                                if let Some(t) = &run.content {
                                    text.push_str(t);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    text
}
