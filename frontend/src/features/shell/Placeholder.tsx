import { EmptyState } from "@/components/EmptyState";

export function Placeholder({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      <EmptyState message={message} />
    </div>
  );
}
