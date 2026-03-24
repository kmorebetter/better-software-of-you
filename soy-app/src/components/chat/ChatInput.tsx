import { useState, useRef, useCallback } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  };

  return (
    <div className="border-t border-zinc-200 px-6 py-4">
      <div className="flex items-end gap-3 bg-zinc-100 rounded-2xl px-4 py-3">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Talk to SoY..."
          disabled={disabled}
          rows={1}
          className="flex-1 bg-transparent text-sm text-zinc-900 placeholder-zinc-400 resize-none outline-none"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="p-1.5 rounded-full bg-zinc-900 text-white disabled:opacity-30 hover:bg-zinc-700 transition-colors"
        >
          <SendHorizontal size={16} />
        </button>
      </div>
    </div>
  );
}
