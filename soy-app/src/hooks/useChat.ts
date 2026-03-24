import { useState, useCallback, useRef } from "react";
import { listen } from "@tauri-apps/api/event";
import { Message, StreamEvent, PanelHint } from "../lib/types";
import { sendMessage } from "../lib/commands";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamBuffer = useRef("");
  const [pendingPanelHint, setPendingPanelHint] = useState<PanelHint | null>(null);

  const send = useCallback(async (content: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    streamBuffer.current = "";

    const unlisten = await listen<StreamEvent>("chat-stream", (event) => {
      const data = event.payload;

      if (data.token) {
        streamBuffer.current += data.token;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, content: streamBuffer.current };
          }
          return updated;
        });
      }

      if (data.panelHint) {
        setPendingPanelHint(data.panelHint);
      }

      if (data.done) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = { ...last, isStreaming: false };
          }
          return updated;
        });
        setIsStreaming(false);
        unlisten();
      }

      if (data.error) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: `Something went wrong: ${data.error}`,
              isStreaming: false,
            };
          }
          return updated;
        });
        setIsStreaming(false);
        unlisten();
      }
    });

    try {
      await sendMessage(content);
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          updated[updated.length - 1] = {
            ...last,
            content: `Failed to send message: ${err}`,
            isStreaming: false,
          };
        }
        return updated;
      });
      setIsStreaming(false);
      unlisten();
    }
  }, []);

  return { messages, isStreaming, send, pendingPanelHint, setPendingPanelHint };
}
