import { Avatar } from "../shared/Avatar";

interface ContactCardProps {
  name: string;
  company?: string;
  role?: string;
  onClick?: () => void;
}

export function ContactCard({ name, company, role, onClick }: ContactCardProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-zinc-50 transition-colors"
    >
      <Avatar name={name} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-900 truncate">{name}</p>
        {(company || role) && (
          <p className="text-xs text-zinc-500 truncate">
            {[role, company].filter(Boolean).join(" at ")}
          </p>
        )}
      </div>
    </button>
  );
}
