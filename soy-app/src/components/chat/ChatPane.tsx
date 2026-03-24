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
      <MessageList messages={messages} />
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
