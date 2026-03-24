use rusqlite::{params, Connection};
use serde_json::Value;
use std::path::PathBuf;
use std::sync::Mutex;

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn new() -> Result<Self, String> {
        let db_path = Self::db_path();

        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create data dir: {}", e))?;
        }

        let conn = Connection::open(&db_path)
            .map_err(|e| format!("Failed to open database: {}", e))?;

        // Enable WAL mode for better concurrent reads
        conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
            .map_err(|e| format!("Failed to set pragmas: {}", e))?;

        let db = Self {
            conn: Mutex::new(conn),
        };
        db.run_migrations()?;
        Ok(db)
    }

    pub fn db_path() -> PathBuf {
        let data_dir = dirs::data_local_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("software-of-you");
        data_dir.join("soy.db")
    }

    fn run_migrations(&self) -> Result<(), String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;

        // Create migrations tracking table
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL UNIQUE,
                applied_at TEXT DEFAULT (datetime('now'))
            )",
        )
        .map_err(|e| format!("Migration table error: {}", e))?;

        // Get list of applied migrations
        let mut stmt = conn
            .prepare("SELECT filename FROM _migrations")
            .map_err(|e| e.to_string())?;
        let applied: Vec<String> = stmt
            .query_map([], |row| row.get(0))
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .collect();

        // Read migration files from the migrations directory
        let migrations_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("migrations");
        if !migrations_dir.exists() {
            return Ok(());
        }

        let mut entries: Vec<_> = std::fs::read_dir(&migrations_dir)
            .map_err(|e| format!("Can't read migrations dir: {}", e))?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().map_or(false, |ext| ext == "sql"))
            .collect();
        entries.sort_by_key(|e| e.file_name());

        for entry in entries {
            let filename = entry.file_name().to_string_lossy().to_string();
            if applied.contains(&filename) {
                continue;
            }

            let sql = std::fs::read_to_string(entry.path())
                .map_err(|e| format!("Can't read {}: {}", filename, e))?;

            conn.execute_batch(&sql)
                .map_err(|e| format!("Migration {} failed: {}", filename, e))?;

            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?1)",
                params![filename],
            )
            .map_err(|e| format!("Can't record migration {}: {}", filename, e))?;
        }

        Ok(())
    }

    /// Execute a query and return results as JSON array
    pub fn query_json(&self, sql: &str, params: &[&dyn rusqlite::ToSql]) -> Result<Value, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        let mut stmt = conn.prepare(sql).map_err(|e| format!("SQL error: {}", e))?;

        let column_names: Vec<String> = stmt
            .column_names()
            .iter()
            .map(|s| s.to_string())
            .collect();

        let rows: Vec<Value> = stmt
            .query_map(params, |row| {
                let mut map = serde_json::Map::new();
                for (i, name) in column_names.iter().enumerate() {
                    let val = row.get_ref(i).unwrap_or(rusqlite::types::ValueRef::Null);
                    let json_val = match val {
                        rusqlite::types::ValueRef::Null => Value::Null,
                        rusqlite::types::ValueRef::Integer(n) => serde_json::json!(n),
                        rusqlite::types::ValueRef::Real(f) => serde_json::json!(f),
                        rusqlite::types::ValueRef::Text(s) => {
                            Value::String(String::from_utf8_lossy(s).to_string())
                        }
                        rusqlite::types::ValueRef::Blob(_) => Value::Null,
                    };
                    map.insert(name.clone(), json_val);
                }
                Ok(Value::Object(map))
            })
            .map_err(|e| format!("Query error: {}", e))?
            .filter_map(|r| r.ok())
            .collect();

        Ok(Value::Array(rows))
    }

    /// Execute a write statement (INSERT, UPDATE, DELETE)
    pub fn execute(&self, sql: &str, params: &[&dyn rusqlite::ToSql]) -> Result<i64, String> {
        let conn = self.conn.lock().map_err(|e| e.to_string())?;
        conn.execute(sql, params)
            .map_err(|e| format!("Execute error: {}", e))?;
        Ok(conn.last_insert_rowid())
    }
}
