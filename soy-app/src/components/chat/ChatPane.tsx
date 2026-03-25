import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { Message } from "../../lib/types";

interface ChatPaneProps {
  messages: Message[];
  isStreaming: boolean;
  onSend: (message: string) => void;
}

export function ChatPane({ messages, isStreaming, onSend }: ChatPaneProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-zinc-100 flex items-center">
        <span className="text-xs font-medium text-zinc-400">Software of You</span>
      </div>
      <MessageList messages={messages} />
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
