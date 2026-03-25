import { Message, PanelHint } from "../../lib/types";
import { StreamingText } from "./StreamingText";

interface MessageBubbleProps {
  message: Message;
  onOpenPanel?: (hint: PanelHint) => void;
}

export function MessageBubble({ message, onOpenPanel: _onOpenPanel }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-zinc-900 text-white"
            : "bg-zinc-100 text-zinc-900"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <StreamingText
            content={message.content}
            isStreaming={message.isStreaming ?? false}
          />
        )}
      </div>
    </div>
  );
}
