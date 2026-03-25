import { X, Pin } from "lucide-react";
import { PanelHint } from "../../lib/types";
import { PanelRouter } from "./PanelRouter";

interface SidePanelProps {
  panel: PanelHint | null;
  isOpen: boolean;
  isPinned: boolean;
  onClose: () => void;
  onTogglePin: () => void;
}

export function SidePanel({ panel, isOpen, isPinned, onClose, onTogglePin }: SidePanelProps) {
  return (
    <div
      className={`border-l border-zinc-200 bg-white transition-all duration-300 ease-in-out overflow-hidden ${
        isOpen ? "w-[480px]" : "w-0"
      }`}
    >
      {panel && (
        <div className="h-full flex flex-col w-[480px]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
            <h2 className="text-sm font-semibold text-zinc-700">
              {panel.title || panel.type}
            </h2>
            <div className="flex items-center gap-1">
              <button
                onClick={onTogglePin}
                className={`p-1.5 rounded-lg hover:bg-zinc-100 ${
                  isPinned ? "text-blue-600" : "text-zinc-400"
                }`}
              >
                <Pin size={14} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400"
              >
                <X size={14} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <PanelRouter panel={panel} />
          </div>
        </div>
      )}
    </div>
  );
}
