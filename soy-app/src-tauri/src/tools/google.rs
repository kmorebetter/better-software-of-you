use serde_json::{json, Value};

pub fn definition() -> Value {
    json!({
        "name": "google",
        "description": "Manage Google integration — check connection status, trigger data sync, or initiate Google sign-in. Use this when the user asks about email/calendar sync or connecting their Google account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "sync", "connect", "sync_transcripts"],
                    "description": "status: check connection + last sync time. sync: trigger immediate Gmail + Calendar sync. connect: start Google OAuth sign-in flow. sync_transcripts: import Google Meet transcripts from Gmail."
                },
                "count": {
                    "type": "integer",
                    "description": "For sync action: number of emails to fetch. Default 50. User can request any amount (e.g. 300, 500, 1000). Respect what they ask for."
                }
            },
            "required": ["action"]
        }
    })
}
