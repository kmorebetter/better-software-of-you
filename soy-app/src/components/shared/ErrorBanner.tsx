import { AlertTriangle, X } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  action?: { label: string; onClick: () => void };
  onDismiss?: () => void;
}

export function ErrorBanner({ message, action, onDismiss }: ErrorBannerProps) {
  return (
    <div className="mx-4 mt-2 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
      <AlertTriangle size={16} className="shrink-0 text-red-500" />
      <p className="flex-1 text-sm text-red-700">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="shrink-0 rounded-lg bg-red-100 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors"
        >
          {action.label}
        </button>
      )}
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="shrink-0 p-1 rounded-lg text-red-400 hover:bg-red-100 transition-colors"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
