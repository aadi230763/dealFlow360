export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 rounded-sm border border-dashed border-border py-12 text-center">
      <p className="text-sm text-ink-muted">{message}</p>
    </div>
  );
}
