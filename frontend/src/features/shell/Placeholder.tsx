import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";

export function Placeholder({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={title} />
      <EmptyState message={message} />
    </div>
  );
}
