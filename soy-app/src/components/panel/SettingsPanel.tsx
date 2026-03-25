import { useCallback, useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import {
  getApiKeyStatus,
  setApiKey,
  getGoogleStatus,
  connectGoogle,
  disconnectGoogle,
} from "../../lib/commands";
import { Badge } from "../shared/Badge";
import { Card } from "../shared/Card";
import {
  KeyRound,
  Database,
  FolderOpen,
  Mail,
  Check,
  Eye,
  EyeOff,
  Info,
  Loader2,
} from "lucide-react";

const APP_VERSION = "0.1.0";

export function SettingsPanel() {
  // API key state
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [isEditingKey, setIsEditingKey] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [keySaved, setKeySaved] = useState(false);
  const [showKey, setShowKey] = useState(false);

  // Google state
  const [googleConnected, setGoogleConnected] = useState<boolean | null>(null);
  const [googleEmail, setGoogleEmail] = useState<string | null>(null);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  // Load initial state
  useEffect(() => {
    getApiKeyStatus()
      .then((s) => setHasKey(s.hasKey))
      .catch(() => setHasKey(false));

    getGoogleStatus()
      .then((s) => {
        setGoogleConnected(s.connected);
        setGoogleEmail(s.email);
      })
      .catch(() => setGoogleConnected(false));
  }, []);

  // Listen for Google connection events (from connect/disconnect commands)
  useEffect(() => {
    const unlistenPromise = listen<{ connected: boolean; email?: string }>(
      "google-connected",
      (event) => {
        setGoogleConnected(event.payload.connected);
        if (event.payload.connected) {
          if (event.payload.email) {
            setGoogleEmail(event.payload.email);
          } else {
            getGoogleStatus()
              .then((s) => setGoogleEmail(s.email))
              .catch(() => {});
          }
        } else {
          setGoogleEmail(null);
          setGoogleLoading(false);
        }
      },
    );

    return () => {
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  // Listen for sync progress events
  useEffect(() => {
    const unlistenPromise = listen<{ status: string; step?: string }>(
      "sync-status",
      (event) => {
        if (event.payload.status === "done") {
          setSyncStatus(null);
          setGoogleLoading(false);
        } else if (event.payload.step === "gmail") {
          setSyncStatus("Syncing emails...");
        } else if (event.payload.step === "calendar") {
          setSyncStatus("Syncing calendar...");
        }
      },
    );

    return () => {
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  const handleSaveKey = useCallback(async () => {
    if (!keyInput.trim()) return;
    try {
      await setApiKey(keyInput.trim());
      setHasKey(true);
      setIsEditingKey(false);
      setKeyInput("");
      setKeySaved(true);
      setTimeout(() => setKeySaved(false), 2000);
    } catch {
      // Key save failed — input stays visible so user can retry
    }
  }, [keyInput]);

  const handleConnectGoogle = useCallback(async () => {
    setGoogleLoading(true);
    try {
      const result = await connectGoogle();
      // The connect command now completes synchronously (localhost callback).
      // The event listener will also fire, but we can set state here too.
      setGoogleConnected(true);
      if (result?.email) {
        setGoogleEmail(result.email);
      }
    } catch {
      // If the user closes the browser or the flow times out
    } finally {
      setGoogleLoading(false);
    }
  }, []);

  const handleDisconnectGoogle = useCallback(async () => {
    setGoogleLoading(true);
    try {
      await disconnectGoogle();
      setGoogleConnected(false);
      setGoogleEmail(null);
    } catch {
      // Disconnect failed
    } finally {
      setGoogleLoading(false);
    }
  }, []);

  return (
    <div className="space-y-5">
      {/* Claude API Key */}
      <section>
        <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
          API Key
        </h3>
        <Card>
          <div className="flex items-center gap-3">
            <KeyRound size={16} className="text-zinc-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-900">Claude API Key</p>
              {hasKey && !isEditingKey && (
                <p className="text-xs text-zinc-500 mt-0.5 font-mono">
                  sk-ant-...****
                </p>
              )}
            </div>
            {hasKey === null ? (
              <span className="text-xs text-zinc-400">Checking...</span>
            ) : keySaved ? (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                <Check size={12} /> Saved
              </span>
            ) : hasKey && !isEditingKey ? (
              <button
                onClick={() => setIsEditingKey(true)}
                className="text-xs text-zinc-500 hover:text-zinc-700 transition-colors"
              >
                Change
              </button>
            ) : (
              <Badge variant="inactive">Not set</Badge>
            )}
          </div>

          {(isEditingKey || !hasKey) && (
            <div className="mt-3 space-y-2">
              <div className="relative">
                <input
                  type={showKey ? "text" : "password"}
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSaveKey()}
                  placeholder="sk-ant-..."
                  className="w-full px-3 py-2 pr-9 rounded-lg bg-zinc-50 border border-zinc-200 text-sm outline-none focus:ring-2 focus:ring-zinc-300 font-mono"
                  autoFocus
                />
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-zinc-400 hover:text-zinc-600"
                >
                  {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleSaveKey}
                  disabled={!keyInput.trim()}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-zinc-900 text-white text-xs font-medium hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Save Key
                </button>
                {isEditingKey && (
                  <button
                    onClick={() => {
                      setIsEditingKey(false);
                      setKeyInput("");
                    }}
                    className="px-3 py-1.5 rounded-lg border border-zinc-200 text-xs text-zinc-600 hover:bg-zinc-50 transition-colors"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          )}
        </Card>
      </section>

      {/* Google Account */}
      <section>
        <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
          Google Account
        </h3>
        <Card>
          <div className="flex items-center gap-3">
            <Mail size={16} className="text-zinc-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-900">Gmail & Calendar</p>
              {googleEmail && (
                <p className="text-xs text-zinc-500 mt-0.5 truncate">
                  {googleEmail}
                </p>
              )}
            </div>
            {googleConnected === null ? (
              <span className="text-xs text-zinc-400">Checking...</span>
            ) : googleConnected ? (
              <Badge variant="active">Connected</Badge>
            ) : (
              <Badge variant="inactive">Not connected</Badge>
            )}
          </div>

          {syncStatus && (
            <div className="mt-2 flex items-center gap-2 px-2 py-1.5 rounded-lg bg-blue-50 text-xs text-blue-700">
              <Loader2 size={12} className="animate-spin" />
              {syncStatus}
            </div>
          )}

          <div className="mt-3">
            {googleConnected ? (
              <button
                onClick={handleDisconnectGoogle}
                disabled={googleLoading}
                className="w-full px-3 py-1.5 rounded-lg border border-red-200 text-xs text-red-600 hover:bg-red-50 disabled:opacity-40 transition-colors"
              >
                {googleLoading ? "Disconnecting..." : "Disconnect Google"}
              </button>
            ) : (
              <button
                onClick={handleConnectGoogle}
                disabled={googleLoading}
                className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 text-white text-xs font-medium hover:bg-zinc-700 disabled:opacity-40 transition-colors"
              >
                {googleLoading
                  ? "Connecting..."
                  : "Connect Google Account"}
              </button>
            )}
          </div>
        </Card>
      </section>

      {/* Data & Storage */}
      <section>
        <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
          Data & Storage
        </h3>

        <Card>
          <div className="flex items-center gap-3">
            <Database size={16} className="text-zinc-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-zinc-900">Database</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                SQLite, stored locally
              </p>
            </div>
          </div>
        </Card>

        <Card className="mt-2">
          <div className="flex items-center gap-3">
            <FolderOpen size={16} className="text-zinc-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-900">Data location</p>
              <p className="text-xs text-zinc-500 mt-0.5 break-all font-mono">
                ~/Library/Application Support/software-of-you/
              </p>
            </div>
          </div>
        </Card>
      </section>

      {/* About */}
      <section>
        <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
          About
        </h3>
        <Card>
          <div className="flex items-center gap-3">
            <Info size={16} className="text-zinc-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-zinc-900">Software of You</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                Version {APP_VERSION}
              </p>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
