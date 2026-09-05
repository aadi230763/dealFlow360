import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Product, QuotationListItem, ReportOut } from "@/api/types";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Select } from "@/components/Select";
import { Button } from "@/components/Button";
import { SkeletonText } from "@/components/Skeleton";
import { getToken } from "@/api/client";
import { STATUS_LABELS, STATUS_ORDER } from "@/features/quotations/statusUtils";

const PERIODS = [
  { label: "Last 7 days", value: "7" },
  { label: "Last 30 days", value: "30" },
  { label: "Last 90 days", value: "90" },
  { label: "All time", value: "" },
];

export function ReportsPage() {
  const [periodDays, setPeriodDays] = useState("30");
  const [ownerUserId, setOwnerUserId] = useState("");
  const [approvalStatus, setApprovalStatus] = useState("");
  const [productId, setProductId] = useState("");

  const { data: quotations } = useQuery({
    queryKey: ["quotations"],
    queryFn: () => api.get<QuotationListItem[]>("/quotations"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });

  const owners = useMemo(() => {
    const map = new Map<string, string>();
    for (const q of quotations ?? []) map.set(q.owner_user_id, q.owner_name);
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [quotations]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (periodDays) params.set("period_days", periodDays);
    if (ownerUserId) params.set("owner_user_id", ownerUserId);
    if (approvalStatus) params.set("approval_status", approvalStatus);
    if (productId) params.set("product_id", productId);
    return params.toString();
  }, [periodDays, ownerUserId, approvalStatus, productId]);

  const { data: report, isLoading } = useQuery({
    queryKey: ["report", queryString],
    queryFn: () => api.get<ReportOut>(`/reports${queryString ? `?${queryString}` : ""}`),
  });

  const exportCsv = () => {
    const token = getToken();
    const url = `/api/reports/export.csv${queryString ? `?${queryString}` : ""}`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((res) => res.blob())
      .then((blob) => {
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = "report.csv";
        a.click();
        URL.revokeObjectURL(href);
      });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Admin / Reporting Dashboard"
        eyebrow="Optional"
        description="Sales trends, approval bottlenecks and platform usage."
      />

      <Card padding="sm" className="flex flex-wrap items-end gap-2">
        <Select id="rp-period" label="Period" value={periodDays} onChange={(e) => setPeriodDays(e.target.value)}>
          {PERIODS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </Select>
        <Select id="rp-owner" label="Sales Team" value={ownerUserId} onChange={(e) => setOwnerUserId(e.target.value)}>
          <option value="">All reps</option>
          {owners.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </Select>
        <Select
          id="rp-status"
          label="Approval Status"
          value={approvalStatus}
          onChange={(e) => setApprovalStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </Select>
        <Select id="rp-product" label="Product" value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">All products</option>
          {products?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
      </Card>

      {isLoading || !report ? (
        <SkeletonText lines={3} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Quotes Created</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">{report.quotes_created}</p>
            <p className="text-xs text-ink-muted">matching current filters</p>
          </Card>
          <Card>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Avg Approval Time</p>
            <p className="mt-1.5 text-2xl font-semibold tabular-nums text-ink">
              {report.avg_approval_time_hours ?? "—"}
              {report.avg_approval_time_hours ? <span className="text-sm text-ink-muted"> hrs</span> : null}
            </p>
            <p className="text-xs text-ink-muted">from real approval timestamps</p>
          </Card>
          <Card>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Top Upsold Product</p>
            <p className="mt-1.5 text-lg font-semibold text-ink">{report.top_upsold_product ?? "—"}</p>
            <p className="text-xs text-ink-muted">most frequent pairing suggestion sold</p>
          </Card>
        </div>
      )}

      <div className="flex justify-end border-t border-border pt-4">
        <Button variant="secondary" onClick={exportCsv}>
          Export CSV
        </Button>
      </div>
    </div>
  );
}
