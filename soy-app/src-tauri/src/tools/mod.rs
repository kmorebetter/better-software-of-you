pub mod calendar;
pub mod contacts;
pub mod email;
pub mod inbox;
pub mod intelligence;
pub mod interactions;
pub mod overview;
pub mod profile;
pub mod search;
pub mod system;
pub mod transcripts;

use crate::db::Database;
use serde_json::Value;
use std::sync::Arc;

/// Execute a tool by name with given arguments, return JSON result
pub fn execute_tool(db: &Arc<Database>, tool_name: &str, args: &Value) -> Result<Value, String> {
    match tool_name {
        "contacts" => contacts::execute(db, args),
        "search" => search::execute(db, args),
        "get_overview" => overview::execute(db),
        "get_profile" => profile::execute(db, args),
        "system_status" => system::execute(db, args),
        "inbox" => inbox::execute(db, args),
        "interactions" => interactions::execute(db, args),
        "email" => email::execute(db, args),
        "calendar" => calendar::execute(db, args),
        "transcripts" => transcripts::execute(db, args),
        "intelligence" => intelligence::execute(db, args),
        _ => Err(format!("Unknown tool: {}", tool_name)),
    }
}

/// Return tool definitions for Claude API (JSON schemas)
pub fn tool_definitions() -> Vec<Value> {
    vec![
        contacts::definition(),
        search::definition(),
        overview::definition(),
        profile::definition(),
        system::definition(),
        inbox::definition(),
        interactions::definition(),
        email::definition(),
        calendar::definition(),
        transcripts::definition(),
        intelligence::definition(),
    ]
}
