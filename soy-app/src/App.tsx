import { useEffect, useState } from "react";
import { ChatPane } from "./components/chat/ChatPane";
import { useChat } from "./hooks/useChat";
import { getApiKeyStatus, setApiKey } from "./lib/commands";
import { KeyRound } from "lucide-react";

function App() {
  const { messages, isStreaming, send } = useChat();
  const [hasKey, setHasKey] = useState<boolean | null>(null);
  const [keyInput, setKeyInput] = useState("");

  useEffect(() => {
    getApiKeyStatus().then((s) => setHasKey(s.hasKey));
  }, []);

  const handleSetKey = async () => {
    if (!keyInput.trim()) return;
    await setApiKey(keyInput.trim());
    setHasKey(true);
  };

  if (hasKey === null) return null;

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
      <div className="flex-1 flex flex-col">
        <ChatPane messages={messages} isStreaming={isStreaming} onSend={send} />
      </div>
    </div>
  );
}

export default App;
