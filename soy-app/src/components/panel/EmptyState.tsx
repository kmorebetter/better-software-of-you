interface EmptyStateProps {
  message: string;
}

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center h-full text-zinc-400 text-sm">
      {message}
    </div>
  );
}
