interface StatGridProps {
  children: React.ReactNode;
}

export function StatGrid({ children }: StatGridProps) {
  return <div className="grid grid-cols-2 gap-2">{children}</div>;
}
