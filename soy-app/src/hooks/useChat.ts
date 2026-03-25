import { useState, useCallback, useRef, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { Message, StreamEvent, PanelHint } from "../lib/types";
import {
  sendMessage,
  createConversation,
  getRecentConversation,
  saveMessage,
} from "../lib/commands";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const streamBuffer = useRef("");
  const [pendingPanelHint, setPendingPanelHint] = useState<PanelHint | null>(
    null,
  );
  const conversationIdRef = useRef<number | null>(null);

  // Keep ref in sync so the send callback always has the latest value
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // Load most recent conversation on mount
  useEffect(() => {
    (async () => {
      try {
        const { conversation, messages: history } =
          await getRecentConversation();
        if (conversation) {
          setConversationId(conversation.id);
          conversationIdRef.current = conversation.id;
          setMessages(
            history.map((m) => ({
              id: crypto.randomUUID(),
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: m.created_at,
            })),
          );
        }
      } catch {
        // Fresh start — no conversation yet
      }
    })();
  }, []);

  const send = useCallback(async (content: string) => {
    // Ensure we have a conversation
    let convId = conversationIdRef.current;
    if (!convId) {
      try {
        const { id } = await createConversation();
        convId = id;
        setConversationId(id);
        conversationIdRef.current = id;
      } catch {
        // Fall back to no persistence
      }
    }

    // Save user message to DB
    if (convId) {
      try {
        await saveMessage(convId, "user", content);
      } catch {
        // Non-fatal: continue even if save fails
      }
    }

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

    // Capture convId for the stream listener closure
    const currentConvId = convId;

    const unlisten = await listen<StreamEvent>("chat-stream", (event) => {
      const data = event.payload;

      if (data.token) {
        streamBuffer.current += data.token;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: streamBuffer.current,
            };
          }
          return updated;
        });
      }

      if (data.panelHint) {
        setPendingPanelHint(data.panelHint);
      }

      if (data.done) {
        // Save the assistant response to DB
        if (currentConvId && streamBuffer.current) {
          saveMessage(currentConvId, "assistant", streamBuffer.current).catch(
            () => {},
          );
        }

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
      await sendMessage(content, currentConvId ?? undefined);
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
