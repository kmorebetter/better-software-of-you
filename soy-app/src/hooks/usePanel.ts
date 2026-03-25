import { useState, useCallback } from "react";
import { PanelHint } from "../lib/types";

export function usePanel() {
  const [panel, setPanel] = useState<PanelHint | null>(null);
  const [isPinned, setIsPinned] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const showPanel = useCallback((hint: PanelHint) => {
    setPanel(hint);
    setIsOpen(true);
  }, []);

  const closePanel = useCallback(() => {
    if (!isPinned) {
      setIsOpen(false);
      setPanel(null);
    }
  }, [isPinned]);

  const togglePin = useCallback(() => {
    setIsPinned((p) => !p);
  }, []);

  return { panel, isOpen, isPinned, showPanel, closePanel, togglePin };
}
