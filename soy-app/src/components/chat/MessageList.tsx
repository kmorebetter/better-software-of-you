import { useEffect, useRef } from "react";
import { Message, PanelHint } from "../../lib/types";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: Message[];
  onOpenPanel?: (hint: PanelHint) => void;
}

export function MessageList({ messages, onOpenPanel }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full text-zinc-400">
          <p className="text-lg font-medium mb-1">Software of You</p>
          <p className="text-sm">Your personal data platform. Say hello.</p>
        </div>
      )}
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onOpenPanel={onOpenPanel} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
