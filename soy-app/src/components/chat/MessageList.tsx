import { useEffect, useRef } from "react";
import { Message, PanelHint } from "../../lib/types";
import { MessageBubble } from "./MessageBubble";
import { WelcomePrompt } from "./WelcomePrompt";

interface MessageListProps {
  messages: Message[];
  onOpenPanel?: (hint: PanelHint) => void;
}

export function MessageList({ messages, onOpenPanel }: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <WelcomePrompt />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onOpenPanel={onOpenPanel} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
