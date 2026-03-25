import { ChevronRight } from "lucide-react";
import { PanelHint } from "../../lib/types";

interface InlineCardProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  panelHint?: PanelHint;
  onOpenPanel?: (hint: PanelHint) => void;
  children?: React.ReactNode;
}

export function InlineCard({ title, subtitle, icon, panelHint, onOpenPanel, children }: InlineCardProps) {
  return (
    <div
      className={`my-3 rounded-xl border border-zinc-200 bg-white p-4 ${
        panelHint ? "cursor-pointer hover:border-zinc-300 hover:shadow-sm transition-all" : ""
      }`}
      onClick={() => panelHint && onOpenPanel?.(panelHint)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {icon && <div className="text-zinc-500">{icon}</div>}
          <div>
            <p className="text-sm font-medium text-zinc-900">{title}</p>
            {subtitle && <p className="text-xs text-zinc-500">{subtitle}</p>}
          </div>
        </div>
        {panelHint && <ChevronRight size={16} className="text-zinc-400" />}
      </div>
      {children && <div className="mt-3 text-sm text-zinc-600">{children}</div>}
    </div>
  );
}
