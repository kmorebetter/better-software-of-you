---
description: Install a new module into Software of You
allowed-tools: ["Bash", "Read", "Write"]
argument-hint: <path to module folder or zip>
---

# Add Module

Walk the user through installing a new Software of You module.

## If $ARGUMENTS Contains a Path

1. Check if the path exists and is a directory or zip file
2. If zip, suggest extracting it first: `unzip <path> -d /tmp/soy-module`
3. Look for `manifest.json` in the module directory
4. Read the manifest and display module details:
   - Name, version, description
   - Features (standalone + enhancements)
   - Required files

5. Copy files to the correct locations:
   - `manifest.json` → `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/modules/{module-name}/manifest.json`
   - Migration `.sql` → `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/migrations/`
   - Command `.md` files → `${CLAUDE_PLUGIN_ROOT:-$(pwd)}/commands/`

6. Run the migration:
   ```
   sqlite3 "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/soy.db" < "${CLAUDE_PLUGIN_ROOT:-$(pwd)}/data/migrations/{migration-file}"
   ```

7. Verify the module registered: `SELECT * FROM modules WHERE name = '{module-name}';`

8. Tell the user:
   - Module installed successfully
   - What new commands are available
   - What cross-module enhancements activated (if any)
   - Suggest restarting the session for full integration

## If No Arguments

Tell the user how module installation works:

"To add a new module, provide the path to the module folder:

`/add-module /path/to/module-folder`

Each module comes as a folder containing a manifest, migration file, and command files. The installer copies everything to the right place and sets up the database tables.

Your current modules:"

Then list installed modules from the database.
