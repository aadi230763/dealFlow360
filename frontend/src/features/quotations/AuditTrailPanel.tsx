import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { AuditEventOut } from "@/api/types";
import { Card } from "@/components/Card";

function formatPayload(payload: Record<string, unknown>): string {
  try {
    return JSON.stringify(payload);
  } catch {
    return "";
  }
}

export function AuditTrailPanel({ entityType, entityId }: { entityType: string; entityId: string }) {
  const { data: events } = useQuery({
    queryKey: ["audit-events", entityType, entityId],
    queryFn: () =>
      api.get<AuditEventOut[]>(`/audit-events?entity_type=${entityType}&entity_id=${entityId}`),
  });

  if (!events || events.length === 0) {
    return <p className="text-sm text-ink-muted">No audit history yet.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-ink-muted">Audit trail</h2>
      <Card padding="none" className="divide-y divide-border">
        {events.map((e) => (
          <div key={e.id} className="px-3.5 py-2.5 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium text-ink">{e.action.replace(/_/g, " ")}</span>
              <span className="tabular-nums text-xs text-ink-muted">
                {new Date(e.created_at).toLocaleString()}
              </span>
            </div>
            <p className="text-xs text-ink-muted">{e.actor_label}</p>
            {Object.keys(e.payload).length > 0 && (
              <p className="mt-1 break-all text-xs text-ink-muted">{formatPayload(e.payload)}</p>
            )}
          </div>
        ))}
      </Card>
    </div>
  );
}
