# Module Manifest Format

Each module declares itself via `modules/{module-name}/manifest.json`.

## Required Fields

```json
{
  "name": "module-name",           // Unique identifier (lowercase, hyphens)
  "display_name": "Module Name",   // Human-readable name
  "version": "1.0.0",              // Semantic version
  "description": "What this module does.",
  "migration": "003_module.sql",   // Migration filename in data/migrations/
  "tables": ["table1", "table2"],  // Tables this module owns
  "entities": ["entity1"],         // Entity types this module introduces
  "commands": ["cmd1", "cmd2"],    // Command files this module provides
  "standalone_features": [         // Features that work without other modules
    "Feature description 1",
    "Feature description 2"
  ],
  "enhancements": [                // Features that activate with other modules
    {
      "requires_module": "other-module",
      "features": ["Enhanced feature 1"],
      "description": "What this enhancement provides."
    }
  ]
}
```

## Enhancement Resolution

The SessionStart hook reads all manifests and checks:
- For each enhancement, is the `requires_module` also installed?
- If yes, that enhancement is "active"
- The active enhancements list is passed to Claude via session context

## Conventions

- Module names are lowercase with hyphens: `project-tracker`, `time-tracker`
- Migration files are numbered sequentially: `001_`, `002_`, `003_`
- Each migration registers itself: `INSERT OR REPLACE INTO modules (name, version) VALUES (?, ?);`
- All migrations are idempotent — safe to re-run
