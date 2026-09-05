import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type {
  DashboardHealthOut,
  DashboardMetricsOut,
  DeliverySlippageOut,
  DiscountAnomalyOut,
  StalledDealOut,
} from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Callout } from "@/components/Callout";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonText } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";

type AlertRow =
  | { kind: "stalled"; key: string; data: StalledDealOut }
  | { kind: "anomaly"; key: string; data: DiscountAnomalyOut }
  | { kind: "slippage"; key: string; data: DeliverySlippageOut };

function issueText(row: AlertRow): string {
  if (row.kind === "stalled") return `Idle ${row.data.idle_days} days`;
  if (row.kind === "anomaly") return `Discount ${row.data.discount_pct}% vs avg ${row.data.baseline_pct}%`;
  return `${row.data.backorder_qty} unit${row.data.backorder_qty === 1 ? "" : "s"} backordered, ${row.data.days_late}d late`;
}

function DiscountByRepChart({ points }: { points: DashboardMetricsOut["discount_by_rep"] }) {
  if (points.length === 0) return <EmptyState message="Not enough discount history yet." />;

  const width = 420;
  const barHeight = 22;
  const gap = 10;
  const labelWidth = 96;
  const plotWidth = width - labelWidth - 48;
  const maxValue = Math.max(...points.map((p) => Number(p.discount_pct)), 1);
  const height = points.length * (barHeight + gap);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Average discount by rep">
      {points.map((p, i) => {
        const value = Number(p.discount_pct);
        const barLen = Math.max(4, (value / maxValue) * plotWidth);
        const y = i * (barHeight + gap);
        const colorClass = p.is_outlier ? "fill-danger" : "fill-primary";
        return (
          <g key={p.rep_name}>
            <text
              x={labelWidth - 8}
              y={y + barHeight / 2 + 4}
              textAnchor="end"
              className="fill-ink-muted text-[11px]"
            >
              {p.rep_name}
            </text>
            <rect x={labelWidth} y={y} width={plotWidth} height={barHeight} rx={4} className="fill-canvas" />
            <rect
              x={labelWidth}
              y={y}
              width={barLen}
              height={barHeight}
              rx={4}
              className={colorClass}
            >
              <title>{`${p.rep_name}: ${value}% avg discount${p.is_outlier ? " (flagged)" : ""}`}</title>
            </rect>
            <text
              x={labelWidth + barLen + 6}
              y={y + barHeight / 2 + 4}
              className="fill-ink text-[11px] font-medium tabular-nums"
            >
              {value}%
            </text>
            {p.is_outlier && (
              <text
                x={width - 4}
                y={y + barHeight / 2 + 4}
                textAnchor="end"
                className="fill-danger text-[10px] font-semibold uppercase tracking-wide"
              >
                Outlier
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function MarginTrendChart({ points }: { points: DashboardMetricsOut["margin_trend"] }) {
  if (points.length < 2) return <EmptyState message="Not enough history yet to show a trend." />;

  const width = 420;
  const height = 160;
  const padX = 8;
  const padTop = 16;
  const padBottom = 24;
  const values = points.map((p) => Number(p.margin_pct));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const plotWidth = width - padX * 2;
  const plotHeight = height - padTop - padBottom;

  const coords = points.map((p, i) => {
    const x = padX + (i / (points.length - 1)) * plotWidth;
    const y = padTop + plotHeight - ((Number(p.margin_pct) - min) / range) * plotHeight;
    return { x, y, point: p };
  });
  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x},${c.y}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1].x},${padTop + plotHeight} L${coords[0].x},${padTop + plotHeight} Z`;
  const last = coords[coords.length - 1];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Margin trend by month">
      <line
        x1={padX}
        y1={padTop + plotHeight}
        x2={width - padX}
        y2={padTop + plotHeight}
        className="stroke-border"
        strokeWidth={1}
      />
      <path d={areaPath} className="fill-primary" fillOpacity={0.1} />
      <path d={linePath} className="stroke-primary" strokeWidth={2} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      {coords.map((c, i) => (
        <circle
          key={i}
          cx={c.x}
          cy={c.y}
          r={i === coords.length - 1 ? 4 : 3}
          className="fill-primary"
          fillOpacity={i === coords.length - 1 ? 1 : 0.6}
          stroke="var(--color-surface)"
          strokeWidth={2}
        >
          <title>{`${c.point.period}: ${c.point.margin_pct}% margin`}</title>
        </circle>
      ))}
      <text x={last.x} y={last.y - 10} textAnchor="end" className="fill-ink text-[11px] font-semibold tabular-nums">
        {last.point.margin_pct}%
      </text>
      {coords.map((c, i) => (
        <text key={i} x={c.x} y={height - 6} textAnchor="middle" className="fill-ink-muted text-[10px]">
          {c.point.period.slice(2)}
        </text>
      ))}
    </svg>
  );
}

export function DealHealthPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  // Nudge/Escalate are a manager-facing follow-up action on a rep's deal, not something a
  // rep should be able to do to themselves or another rep -- the backend enforces this too
  // (require_role on both endpoints), this just keeps a rep from seeing a button that 403s.
  const canAct = user?.role === "SALES_MANAGER" || user?.role === "FINANCE" || user?.role === "ADMIN";

  const { data: health, isLoading } = useQuery({
    queryKey: ["dashboard-health"],
    queryFn: () => api.get<DashboardHealthOut>("/dashboard/health"),
  });
  const { data: metrics } = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: () => api.get<DashboardMetricsOut>("/dashboard/metrics"),
  });

  const actionMutation = useMutation({
    mutationFn: ({ quotationId, action }: { quotationId: string; action: "nudge" | "escalate" }) =>
      api.post(`/quotations/${quotationId}/${action}`),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["dashboard-health"] });
      qc.invalidateQueries({ queryKey: ["audit-events"] });
      toast.push(variables.action === "nudge" ? "Nudge sent" : "Escalated to manager");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Action failed", "risk"),
  });

  const [busyKey, setBusyKey] = useState<string | null>(null);

  const rows: AlertRow[] = useMemo(() => {
    if (!health) return [];
    const stalled: AlertRow[] = health.stalled.map((d) => ({ kind: "stalled", key: `s-${d.quotation_id}`, data: d }));
    const anomalies: AlertRow[] = health.anomalies.map((d) => ({
      kind: "anomaly",
      key: `a-${d.quotation_id}`,
      data: d,
    }));
    const slippage: AlertRow[] = health.slippage.map((d) => ({
      kind: "slippage",
      key: `f-${d.fulfillment_id}`,
      data: d,
    }));
    return [...stalled, ...anomalies, ...slippage].sort(
      (a, b) => new Date(b.data.flagged_at).getTime() - new Date(a.data.flagged_at).getTime(),
    );
  }, [health]);

  const act = (row: AlertRow, action: "nudge" | "escalate") => {
    setBusyKey(row.key);
    actionMutation.mutate(
      { quotationId: row.data.quotation_id, action },
      { onSettled: () => setBusyKey(null) },
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Deal Health and Anomaly Dashboard"
        description="Real-time flags for stalled deals and unusual discount patterns."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Stalled Deals</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">{health?.stalled.length ?? "—"}</p>
          <p className="text-xs text-ink-muted">quotes idle past threshold</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Discount Anomalies</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-danger">{health?.anomalies.length ?? "—"}</p>
          <p className="text-xs text-ink-muted">above rep baseline</p>
        </Card>
        <Card>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Delivery Slippage</p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-warning">{health?.slippage.length ?? "—"}</p>
          <p className="text-xs text-ink-muted">promise dates at risk</p>
        </Card>
      </div>

      {isLoading ? (
        <SkeletonText lines={5} />
      ) : rows.length === 0 ? (
        <EmptyState message="Nothing flagged right now — deals are healthy." />
      ) : (
        <Card padding="none" className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-3.5 py-2.5">Deal</th>
                <th className="px-3.5 py-2.5">Issue</th>
                <th className="px-3.5 py-2.5">Flagged</th>
                <th className="px-3.5 py-2.5">Action</th>
                <th className="px-3.5 py-2.5" />
              </tr>
            </thead>
            <tbody className="[&>tr]:border-b [&>tr]:border-border [&>tr]:transition-colors [&>tr:hover]:bg-canvas [&>tr:last-child]:border-0">
              {rows.map((row) => (
                <tr key={row.key}>
                  <td className="px-3.5 py-2.5">
                    <Link to={`/quotations/${row.data.quotation_id}`} className="font-medium text-primary hover:underline">
                      {row.data.customer_name} — {row.data.number}
                    </Link>
                  </td>
                  <td className="px-3.5 py-2.5 text-ink">{issueText(row)}</td>
                  <td className="px-3.5 py-2.5 tabular-nums text-ink-muted">
                    {new Date(row.data.flagged_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </td>
                  <td className="px-3.5 py-2.5">
                    {row.data.last_action ? (
                      <Badge tone="accent">{row.data.last_action}</Badge>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="px-3.5 py-2.5">
                    {canAct ? (
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="primary"
                          onClick={() => act(row, "nudge")}
                          disabled={busyKey === row.key}
                        >
                          Nudge Rep
                        </Button>
                        <Button
                          variant="danger"
                          onClick={() => act(row, "escalate")}
                          disabled={busyKey === row.key}
                        >
                          Escalate
                        </Button>
                      </div>
                    ) : (
                      <span className="block text-right text-xs text-ink-faint">Manager/Finance only</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {metrics && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <h2 className="mb-3 text-sm font-semibold text-ink">Discount distribution by rep</h2>
            <DiscountByRepChart points={metrics.discount_by_rep} />
          </Card>
          <Card>
            <h2 className="mb-3 text-sm font-semibold text-ink">Margin trend</h2>
            <MarginTrendChart points={metrics.margin_trend} />
          </Card>
        </div>
      )}

      <Callout tone="neutral">
        Anomalies use a z-score against each rep's own discounting history; a rep with too few
        quotes to establish a baseline is instead compared to the org-wide average.
      </Callout>
    </div>
  );
}
