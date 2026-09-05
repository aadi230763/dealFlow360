import type { ReactNode } from "react";
import { InboxIcon } from "@/components/icons";

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-14 text-center">
      <InboxIcon width={22} height={22} className="text-ink-faint" />
      <p className="max-w-xs text-sm text-ink-muted">{message}</p>
      {action}
    </div>
  );
}
