import { useEffect, useState } from "react";
import { getApiKeyStatus } from "../../lib/commands";
import { Badge } from "../shared/Badge";
import { Card } from "../shared/Card";
import { KeyRound, Database, FolderOpen } from "lucide-react";

export function SettingsPanel() {
  const [hasKey, setHasKey] = useState<boolean | null>(null);

  useEffect(() => {
    getApiKeyStatus()
      .then((s) => setHasKey(s.hasKey))
      .catch(() => setHasKey(false));
  }, []);

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-zinc-700">Settings</h3>

      <Card>
        <div className="flex items-center gap-3">
          <KeyRound size={16} className="text-zinc-400" />
          <div className="flex-1">
            <p className="text-sm text-zinc-900">Claude API Key</p>
          </div>
          {hasKey === null ? (
            <span className="text-xs text-zinc-400">Checking...</span>
          ) : hasKey ? (
            <Badge variant="active">Connected</Badge>
          ) : (
            <Badge variant="inactive">Not set</Badge>
          )}
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <Database size={16} className="text-zinc-400" />
          <div className="flex-1">
            <p className="text-sm text-zinc-900">Database</p>
            <p className="text-xs text-zinc-500 mt-0.5">SQLite, stored locally</p>
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-3">
          <FolderOpen size={16} className="text-zinc-400" />
          <div className="flex-1">
            <p className="text-sm text-zinc-900">Data location</p>
            <p className="text-xs text-zinc-500 mt-0.5 break-all">
              ~/Library/Application Support/software-of-you/
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
