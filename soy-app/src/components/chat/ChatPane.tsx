import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { Message, PanelHint } from "../../lib/types";

interface ChatPaneProps {
  messages: Message[];
  isStreaming: boolean;
  onSend: (message: string) => void;
  onOpenPanel?: (hint: PanelHint) => void;
}

export function ChatPane({ messages, isStreaming, onSend, onOpenPanel }: ChatPaneProps) {
  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} onOpenPanel={onOpenPanel} />
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
