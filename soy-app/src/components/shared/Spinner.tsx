export function Spinner() {
  return (
    <div className="flex items-center gap-1.5 py-2">
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.3s]" />
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.15s]" />
      <div className="h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" />
    </div>
  );
}
