export function WelcomePrompt() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-sm">
        <div className="text-4xl mb-4 text-zinc-300 font-light tracking-widest">
          &#9698; &#9698;
        </div>
        <h2 className="text-lg font-semibold text-zinc-700 mb-2">
          Software of You
        </h2>
        <p className="text-sm text-zinc-400 mb-6">
          Your personal data platform. Ask me anything about your contacts,
          emails, calendar, or projects.
        </p>
        <div className="space-y-2 text-sm text-zinc-500">
          <p className="italic">&ldquo;Show my dashboard&rdquo;</p>
          <p className="italic">&ldquo;What&rsquo;s on my calendar this week?&rdquo;</p>
          <p className="italic">&ldquo;Add a contact named Sarah Chen&rdquo;</p>
        </div>
      </div>
    </div>
  );
}
