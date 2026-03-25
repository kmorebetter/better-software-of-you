import { Badge } from "../shared/Badge";
import { CircleCheck } from "lucide-react";

interface Commitment {
  id: number;
  description: string;
  status?: string;
  urgency?: string;
  deadline_date?: string;
  owner_name?: string;
  is_user_commitment?: boolean | number;
}

interface CommitmentListProps {
  commitments: Commitment[];
}

function urgencyVariant(u?: string): "urgent" | "soon" | "awareness" | "default" {
  if (u === "overdue") return "urgent";
  if (u === "soon") return "soon";
  if (u === "upcoming") return "awareness";
  return "default";
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function CommitmentList({ commitments }: CommitmentListProps) {
  if (!commitments.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-zinc-400">
        <CircleCheck size={20} />
        <p className="text-sm">No open commitments</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-zinc-100">
      {commitments.map((c) => (
        <div key={c.id} className="py-2.5 px-1">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm text-zinc-900 flex-1">{c.description}</p>
            {c.urgency && (
              <Badge variant={urgencyVariant(c.urgency)}>
                {c.urgency}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
            {c.owner_name && <span>{c.is_user_commitment ? "You" : c.owner_name}</span>}
            {c.deadline_date && <span>Due {formatDate(c.deadline_date)}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
