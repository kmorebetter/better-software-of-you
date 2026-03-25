import { useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { ChatPane } from "./components/chat/ChatPane";
import { MenuBarWindow } from "./components/menubar/MenuBarWindow";
import { SidePanel } from "./components/panel/SidePanel";
import { ErrorBanner } from "./components/shared/ErrorBanner";
import { LoadingScreen } from "./components/shared/LoadingScreen";
import { useChat } from "./hooks/useChat";
import { usePanel } from "./hooks/usePanel";
import { getApiKeyStatus, getOnboardingState, setApiKey } from "./lib/commands";
import { KeyRound } from "lucide-react";

/** Detect which Tauri window we are running in. */
const currentWindowLabel = getCurrentWindow().label;

function App() {
  // Render the compact menu-bar view when hosted in the "menubar" window.
  if (currentWindowLabel === "menubar") {
    return <MenuBarWindow />;
  }

  return <MainApp />;
}

function MainApp() {
  const { messages, isStreaming, send, error, dismissError, pendingPanelHint, setPendingPanelHint } = useChat();
  const { panel, isOpen, isPinned, showPanel, closePanel, togglePin } = usePanel();
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const onboardingTriggered = useRef(false);

  // React to panel hints from chat
  useEffect(() => {
    if (pendingPanelHint) {
      showPanel(pendingPanelHint);
      setPendingPanelHint(null);
    }
  }, [pendingPanelHint, showPanel, setPendingPanelHint]);

  useEffect(() => {
    getApiKeyStatus().then((s) => setHasKey(s.hasKey));
  }, []);

  // Detect first-run and auto-trigger onboarding conversation
  useEffect(() => {
    if (hasKey && !onboardingTriggered.current) {
      onboardingTriggered.current = true;
      getOnboardingState().then((state) => {
        if (state.stage === "fresh" || state.stage === "has_profile") {
          send("Hello");
        }
      });
    }
  }, [hasKey, send]);

  // Cmd+, keyboard shortcut to open Settings panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey && e.key === ",") {
        e.preventDefault();
        showPanel({ type: "settings", title: "Settings" });
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showPanel]);

  // Listen for "open-settings" events dispatched from error actions
  useEffect(() => {
    const handleOpenSettings = () => {
      showPanel({ type: "settings", title: "Settings" });
    };
    window.addEventListener("open-settings", handleOpenSettings);
    return () => window.removeEventListener("open-settings", handleOpenSettings);
  }, [showPanel]);

  const handleSetKey = async () => {
    if (!keyInput.trim()) return;
    await setApiKey(keyInput.trim());
    setHasKey(true);
  };

  if (hasKey === null) return <LoadingScreen />;

  if (!hasKey) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="max-w-md w-full px-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-zinc-100 mb-4">
              <KeyRound size={24} className="text-zinc-600" />
            </div>
            <h1 className="text-xl font-semibold text-zinc-900">Software of You</h1>
            <p className="text-sm text-zinc-500 mt-1">Enter your Claude API key to get started.</p>
          </div>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSetKey()}
            placeholder="sk-ant-..."
            className="w-full px-4 py-3 rounded-xl bg-zinc-100 text-sm outline-none focus:ring-2 focus:ring-zinc-300"
          />
          <button
            onClick={handleSetKey}
            className="w-full mt-3 px-4 py-3 rounded-xl bg-zinc-900 text-white text-sm font-medium hover:bg-zinc-700 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      <div className="flex-1 flex flex-col min-w-0">
        {error && (
          <ErrorBanner
            message={error.message}
            action={
              error.action
                ? error.action
                : undefined
            }
            onDismiss={dismissError}
          />
        )}
        <ChatPane messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
      <SidePanel
        panel={panel}
        isOpen={isOpen}
        isPinned={isPinned}
        onClose={closePanel}
        onTogglePin={togglePin}
      />
    </div>
  );
}

export default App;
