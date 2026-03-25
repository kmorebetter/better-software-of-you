import { ContactCard } from "./ContactCard";

interface Contact {
  id: number;
  name: string;
  company?: string;
  role?: string;
}

interface ContactListProps {
  contacts: Contact[];
  onSelect?: (id: number) => void;
}

export function ContactList({ contacts, onSelect }: ContactListProps) {
  if (!contacts.length) {
    return <p className="text-sm text-zinc-400 py-4 text-center">No contacts yet</p>;
  }

  return (
    <div className="space-y-0.5">
      {contacts.map((c) => (
        <ContactCard
          key={c.id}
          name={c.name}
          company={c.company}
          role={c.role}
          onClick={() => onSelect?.(c.id)}
        />
      ))}
    </div>
  );
}
