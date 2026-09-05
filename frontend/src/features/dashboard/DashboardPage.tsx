import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import type { AuditEventOut, QuotationListItem, SystemSetting } from "@/api/types";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { SkeletonText } from "@/components/Skeleton";
import { daysSince, TERMINAL_STATUSES } from "@/features/quotations/statusUtils";

function describeEvent(event: AuditEventOut): string {
  const entity = event.entity_type.replace(/_/g, " ");
  const action = event.action.replace(/_/g, " ");
  switch (event.entity_type) {
    case "quotation":
      if (event.action === "submit") return `Quotation ${event.payload.number ?? event.entity_id} routed for approval`;
      if (event.action === "status_change")
        return `Quotation ${event.entity_id.slice(0, 8)} moved ${event.payload.from} → ${event.payload.to}`;
      if (event.action === "recompute")
        return `Quotation ${event.entity_id.slice(0, 8)} recomputed (${event.payload.status_from} → ${event.payload.status_to})`;
      return `Quotation ${event.payload.number ?? event.entity_id.slice(0, 8)} ${action}`;
    case "approval_request":
      return `Approval ${action} by ${event.actor_label}`;
    case "category_tier_ceiling":
      return `Ceiling updated to ${event.payload.ceiling_pct}%`;
    case "stock_level":
      return `Stock updated (on hand: ${event.payload.on_hand})`;
    default:
      return `${entity} ${action}`;
  }
}

export function DashboardPage() {
  const { data: quotations } = useQuery({
    queryKey: ["quotations"],
    queryFn: () => api.get<QuotationListItem[]>("/quotations"),
  });
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SystemSetting[]>("/settings"),
  });
  const { data: activity } = useQuery({
    queryKey: ["audit-events", "recent"],
    queryFn: () => api.get<AuditEventOut[]>("/audit-events?limit=15"),
  });

  const stalledThreshold = useMemo(() => {
    const setting = settings?.find((s) => s.key === "stalled_deal_day_threshold");
    return typeof setting?.value === "number" ? setting.value : 10;
  }, [settings]);

  const kpis = useMemo(() => {
    const list = quotations ?? [];
    const pending = list.filter((q) => q.status === "PENDING_APPROVAL").length;
    const open = list.filter((q) => !TERMINAL_STATUSES.includes(q.status)).length;
    const atRisk = list.filter(
      (q) => !TERMINAL_STATUSES.includes(q.status) && daysSince(q.last_activity_at) > stalledThreshold,
    ).length;
    return { pending, open, atRisk };
  }, [quotations, stalledThreshold]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Sales Dashboard" description="Central hub, links out to every module below." />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card interactive>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Pending Approvals</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">{kpis.pending}</p>
          <p className="text-xs text-ink-muted">quotations waiting</p>
        </Card>
        <Card interactive>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Open Quotations</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">{kpis.open}</p>
          <p className="text-xs text-ink-muted">active deals</p>
        </Card>
        <Card interactive>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">At-Risk Deals</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-danger">{kpis.atRisk}</p>
          <p className="text-xs text-ink-muted">flagged by Deal Health</p>
        </Card>
      </div>

      <div className="flex gap-2">
        <Link to="/quotations/new">
          <Button>+ New Quotation</Button>
        </Link>
        <Link to="/approvals">
          <Button variant="secondary">View Approvals</Button>
        </Link>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-ink-muted">Recent Activity</h2>
        <Card padding="none">
          {!activity ? (
            <div className="p-4">
              <SkeletonText lines={4} />
            </div>
          ) : (
            <div className="flex flex-col divide-y divide-border">
              {activity.map((event) => (
                <div key={event.id} className="flex items-center justify-between px-3.5 py-2.5 text-sm">
                  <span className="text-ink">{describeEvent(event)}</span>
                  <span className="tabular-nums text-xs text-ink-muted">
                    {new Date(event.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
              {activity.length === 0 && <p className="px-3.5 py-4 text-sm text-ink-muted">No activity yet.</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
