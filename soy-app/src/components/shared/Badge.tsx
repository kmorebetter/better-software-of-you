type Variant =
  | "urgent"
  | "soon"
  | "awareness"
  | "overdue"
  | "active"
  | "inactive"
  | "open"
  | "completed"
  | "default";

const styles: Record<Variant, string> = {
  urgent: "bg-red-50 text-red-700 ring-red-200",
  overdue: "bg-red-50 text-red-700 ring-red-200",
  soon: "bg-amber-50 text-amber-700 ring-amber-200",
  open: "bg-amber-50 text-amber-700 ring-amber-200",
  awareness: "bg-blue-50 text-blue-700 ring-blue-200",
  active: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  inactive: "bg-zinc-50 text-zinc-500 ring-zinc-200",
  default: "bg-zinc-50 text-zinc-600 ring-zinc-200",
};

interface BadgeProps {
  variant?: Variant;
  children: React.ReactNode;
}

export function Badge({ variant = "default", children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[variant]}`}
    >
      {children}
    </span>
  );
}
