import { useState, useCallback, useRef, useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { Message, StreamEvent, PanelHint } from "../lib/types";
import {
  sendMessage,
  createConversation,
  getRecentConversation,
  saveMessage,
} from "../lib/commands";

export interface ChatError {
  message: string;
  action?: { label: string; onClick: () => void };
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const streamBuffer = useRef("");
  const [pendingPanelHint, setPendingPanelHint] = useState<PanelHint | null>(
    null,
  );
  const conversationIdRef = useRef<number | null>(null);
  const lastSentMessage = useRef<string>("");

  // Keep ref in sync so the send callback always has the latest value
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const dismissError = useCallback(() => setError(null), []);

  // Parse error messages from the backend into user-friendly ChatError objects
  const parseError = useCallback((errStr: string): ChatError => {
    const lower = errStr.toLowerCase();

    // API key issues
    if (lower.includes("invalid") && lower.includes("key") || lower.includes("401") || lower.includes("authentication")) {
      return {
        message: "Your API key appears to be invalid. Check Settings to update it.",
        action: { label: "Open Settings", onClick: () => {
          // This will be handled by the component that consumes the error
          window.dispatchEvent(new CustomEvent("open-settings"));
        }},
      };
    }

    // Rate limiting
    if (lower.includes("429") || lower.includes("rate limit")) {
      return {
        message: "Rate limited. Please wait a moment and try again.",
      };
    }

    // Server errors
    if (lower.includes("500") || lower.includes("502") || lower.includes("503") || lower.includes("server")) {
      return {
        message: "Claude is having trouble right now. Try again in a few seconds.",
      };
    }

    // Network errors
    if (lower.includes("network") || lower.includes("connect") || lower.includes("timeout") || lower.includes("dns") || lower.includes("fetch")) {
      return {
        message: "Can't reach Claude. Check your internet connection.",
      };
    }

    // No API key
    if (lower.includes("no api key")) {
      return {
        message: "No API key set. Add your Claude API key in Settings.",
        action: { label: "Open Settings", onClick: () => {
          window.dispatchEvent(new CustomEvent("open-settings"));
        }},
      };
    }

    // Generic fallback
    return { message: errStr };
  }, []);

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
    // Clear any previous error when sending a new message
    setError(null);
    lastSentMessage.current = content;

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
        const chatError = parseError(data.error);
        setError(chatError);

        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: chatError.message,
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
      const errStr = String(err);
      const chatError = parseError(errStr);
      setError(chatError);

      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          updated[updated.length - 1] = {
            ...last,
            content: chatError.message,
            isStreaming: false,
          };
        }
        return updated;
      });
      setIsStreaming(false);
      unlisten();
    }
  }, [parseError]);

  return { messages, isStreaming, send, error, dismissError, pendingPanelHint, setPendingPanelHint };
}
