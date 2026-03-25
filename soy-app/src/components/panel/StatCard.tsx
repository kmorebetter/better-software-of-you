import { type LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  muted?: boolean;
}

export function StatCard({ label, value, icon: Icon, muted }: StatCardProps) {
  return (
    <div className="rounded-lg border border-zinc-100 bg-zinc-50/50 p-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon size={14} className="text-zinc-400" />}
        <span className="text-xs text-zinc-500">{label}</span>
      </div>
      <p className={`mt-1 text-lg font-semibold ${muted ? "text-zinc-400" : "text-zinc-900"}`}>
        {value ?? "\u2014"}
      </p>
    </div>
  );
}
