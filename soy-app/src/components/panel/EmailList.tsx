import { Mail, ArrowUpRight, ArrowDownLeft } from "lucide-react";

interface Email {
  id: number;
  subject?: string;
  direction?: string;
  received_at?: string;
  snippet?: string;
  read_at?: string;
}

interface EmailListProps {
  emails: Email[];
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function EmailList({ emails }: EmailListProps) {
  if (!emails.length) {
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-zinc-400">
        <Mail size={20} />
        <p className="text-sm">No emails</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-zinc-100">
      {emails.map((email) => {
        const isInbound = email.direction === "inbound";
        const unread = isInbound && !email.read_at;
        const DirIcon = isInbound ? ArrowDownLeft : ArrowUpRight;
        return (
          <div key={email.id} className="flex items-start gap-2.5 py-2.5 px-1">
            <DirIcon
              size={14}
              className={`mt-0.5 shrink-0 ${isInbound ? "text-blue-500" : "text-zinc-400"}`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className={`text-sm truncate ${unread ? "font-semibold text-zinc-900" : "text-zinc-700"}`}>
                  {email.subject || "(no subject)"}
                </p>
                <span className="text-xs text-zinc-400 shrink-0">
                  {formatDate(email.received_at)}
                </span>
              </div>
              {email.snippet && (
                <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{email.snippet}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
