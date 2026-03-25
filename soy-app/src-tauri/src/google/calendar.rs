use crate::db::Database;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

// ---------------------------------------------------------------------------
// Google Calendar API response types
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct EventList {
    items: Option<Vec<CalendarEvent>>,
}

#[derive(Debug, Deserialize)]
struct CalendarEvent {
    id: Option<String>,
    summary: Option<String>,
    description: Option<String>,
    location: Option<String>,
    start: Option<EventTime>,
    end: Option<EventTime>,
    status: Option<String>,
    attendees: Option<Vec<Attendee>>,
}

#[derive(Debug, Deserialize)]
struct EventTime {
    #[serde(rename = "dateTime")]
    date_time: Option<String>,
    date: Option<String>,
}

#[derive(Debug, Deserialize)]
struct Attendee {
    email: Option<String>,
    #[serde(rename = "displayName")]
    display_name: Option<String>,
    #[serde(rename = "responseStatus")]
    response_status: Option<String>,
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

/// Fetch calendar events from 7 days ago to 14 days ahead and upsert locally.
pub async fn sync_calendar(
    db: &Arc<Database>,
    access_token: &str,
) -> Result<SyncResult, String> {
    let client = reqwest::Client::new();

    // Build time window: 7 days ago → 14 days ahead.
    let now = chrono::Utc::now();
    let time_min = (now - chrono::Duration::days(7))
        .format("%Y-%m-%dT%H:%M:%SZ")
        .to_string();
    let time_max = (now + chrono::Duration::days(14))
        .format("%Y-%m-%dT%H:%M:%SZ")
        .to_string();

    let url = format!(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events?\
         timeMin={}&timeMax={}&singleEvents=true&orderBy=startTime&maxResults=100",
        urlencoding::encode(&time_min),
        urlencoding::encode(&time_max),
    );

    let resp = client
        .get(&url)
        .bearer_auth(access_token)
        .send()
        .await
        .map_err(|e| format!("Calendar list request failed: {}", e))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("Calendar list failed ({}): {}", status, body));
    }

    let event_list: EventList = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse calendar events: {}", e))?;

    let events = match event_list.items {
        Some(items) => items,
        None => {
            update_sync_timestamp(db)?;
            return Ok(SyncResult {
                synced: 0,
                linked: 0,
                errors: 0,
            });
        }
    };

    let mut synced: usize = 0;
    let mut linked: usize = 0;
    let mut errors: usize = 0;

    for event in &events {
        let google_event_id = match &event.id {
            Some(id) => id.clone(),
            None => {
                errors += 1;
                continue;
            }
        };

        let title = event.summary.clone().unwrap_or_else(|| "(No title)".to_string());
        let description = event.description.clone();
        let location = event.location.clone();

        // Parse start/end times. Prefer dateTime; fall back to all-day date.
        let (start_time, all_day) = match &event.start {
            Some(t) => {
                if let Some(ref dt) = t.date_time {
                    (dt.clone(), 0i32)
                } else if let Some(ref d) = t.date {
                    (d.clone(), 1i32)
                } else {
                    (String::new(), 0i32)
                }
            }
            None => (String::new(), 0i32),
        };

        let end_time = match &event.end {
            Some(t) => t
                .date_time
                .clone()
                .or_else(|| t.date.clone())
                .unwrap_or_default(),
            None => String::new(),
        };

        let status = event.status.clone().unwrap_or_else(|| "confirmed".to_string());

        // Build attendees JSON and match contacts.
        let mut attendee_entries: Vec<serde_json::Value> = Vec::new();
        let mut contact_ids: Vec<i64> = Vec::new();

        if let Some(ref attendees) = event.attendees {
            for attendee in attendees {
                let email = attendee.email.clone().unwrap_or_default();
                let name = attendee.display_name.clone().unwrap_or_default();
                let rsvp = attendee.response_status.clone().unwrap_or_default();

                attendee_entries.push(serde_json::json!({
                    "email": email,
                    "name": name,
                    "status": rsvp,
                }));

                // Try to match attendee to a contact.
                if !email.is_empty() {
                    if let Ok(Some(cid)) = find_contact_by_email(db, &email) {
                        contact_ids.push(cid);
                    }
                }
            }
        }

        if !contact_ids.is_empty() {
            linked += 1;
        }

        let attendees_json = serde_json::to_string(&attendee_entries).unwrap_or_else(|_| "[]".to_string());
        let contact_ids_json = serde_json::to_string(&contact_ids).unwrap_or_else(|_| "[]".to_string());

        // Upsert into calendar_events.
        let result = db.execute(
            "INSERT OR REPLACE INTO calendar_events (
                google_event_id, calendar_id, title, description, location,
                start_time, end_time, all_day, status,
                attendees, contact_ids, synced_at
            ) VALUES (?1, 'primary', ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now'))",
            &[
                &google_event_id as &dyn rusqlite::ToSql,
                &title,
                &description,
                &location,
                &start_time,
                &end_time,
                &all_day,
                &status,
                &attendees_json,
                &contact_ids_json,
            ],
        );

        match result {
            Ok(_) => synced += 1,
            Err(e) => {
                eprintln!("Calendar upsert error for {}: {}", google_event_id, e);
                errors += 1;
            }
        }
    }

    // Update the sync timestamp.
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
         VALUES ('calendar_last_synced', datetime('now'), datetime('now'))",
        &[],
    )?;
    Ok(())
}
