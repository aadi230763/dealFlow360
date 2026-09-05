import { EmptyState } from "@/components/EmptyState";

export function PortalMessagesPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight text-ink">Messages</h1>
      <EmptyState message="Comments and requests you submit from My Quotation show up here as a thread in a future update. For now, use My Quotation to talk to your sales contact." />
    </div>
  );
}
