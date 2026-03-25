import { useEffect, useState } from "react";
import { getPanelData } from "../../lib/commands";
import { EmailList } from "./EmailList";

/* eslint-disable @typescript-eslint/no-explicit-any */

export function EmailPanel() {
  const [emails, setEmails] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPanelData("email")
      .then((data: any) => setEmails(data?.emails ?? []))
      .catch(() => setEmails([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-zinc-400 py-8 text-center">Loading...</p>;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-zinc-700">Emails</h3>
      <EmailList emails={emails} />
    </div>
  );
}
