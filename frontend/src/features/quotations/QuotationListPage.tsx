import { useMemo, useState, type DragEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { QuotationListItem, QuotationStatus, SystemSetting } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Money } from "@/components/Money";
import { Percent } from "@/components/Percent";
import { Select } from "@/components/Select";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Callout } from "@/components/Callout";
import { SkeletonText } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  KANBAN_COLUMNS,
  KANBAN_LABELS,
  TERMINAL_STATUSES,
  statusTone,
  daysSince,
  kanbanColumnFor,
} from "./statusUtils";

type ViewMode = "kanban" | "table";

export function QuotationListPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [view, setView] = useState<ViewMode>("kanban");

  const {
    data: quotations,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["quotations"],
    queryFn: () => api.get<QuotationListItem[]>("/quotations"),
  });
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SystemSetting[]>("/settings"),
  });

  const stalledThreshold = useMemo(() => {
    const setting = settings?.find((s) => s.key === "stalled_deal_day_threshold");
    return typeof setting?.value === "number" ? setting.value : 10;
  }, [settings]);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: QuotationStatus }) =>
      api.put(`/quotations/${id}/status`, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quotations"] });
      toast.push("Quotation moved");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Move failed", "risk"),
  });

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [ownerFilter, setOwnerFilter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const owners = useMemo(() => {
    const map = new Map<string, string>();
    for (const q of quotations ?? []) map.set(q.owner_user_id, q.owner_name);
    return Array.from(map, ([id, name]) => ({ id, name }));
  }, [quotations]);

  const filtered = useMemo(() => {
    return (quotations ?? []).filter((q) => {
      if (statusFilter && q.status !== statusFilter) return false;
      if (ownerFilter && q.owner_user_id !== ownerFilter) return false;
      if (dateFrom && new Date(q.created_at) < new Date(dateFrom)) return false;
      if (dateTo && new Date(q.created_at) > new Date(dateTo + "T23:59:59")) return false;
      return true;
    });
  }, [quotations, statusFilter, ownerFilter, dateFrom, dateTo]);

  const columns = useMemo(() => {
    const map = new Map<QuotationStatus, QuotationListItem[]>();
    for (const s of KANBAN_COLUMNS) map.set(s, []);
    for (const q of quotations ?? []) {
      const col = kanbanColumnFor(q.status);
      if (col) map.get(col)?.push(q);
    }
    return map;
  }, [quotations]);

  const onDragStart = (e: DragEvent<HTMLDivElement>, id: string) => {
    e.dataTransfer.setData("text/quotation-id", id);
  };
  const onDrop = (e: DragEvent<HTMLDivElement>, status: QuotationStatus) => {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/quotation-id");
    if (id) statusMutation.mutate({ id, status });
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Quotations"
        description="Every quotation in the system, one row per quotation, click a row to open it."
        actions={
          <>
            <Link to="/quotations/new">
              <Button>+ New Quotation</Button>
            </Link>
            <Button variant="secondary" onClick={() => setView(view === "kanban" ? "table" : "kanban")}>
              {view === "kanban" ? "Switch to Table View" : "Switch to Kanban"}
            </Button>
          </>
        }
      />

      {isLoading ? (
        <SkeletonText lines={5} />
      ) : isError ? (
        <Callout tone="danger">
          Couldn't load quotations: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
        </Callout>
      ) : (quotations ?? []).length === 0 ? (
        <EmptyState message="No quotations yet. Create one to see approval routing in action." />
      ) : view === "kanban" ? (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {KANBAN_COLUMNS.map((status) => {
            const cards = columns.get(status) ?? [];
            return (
              <div
                key={status}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDrop(e, status)}
                className="flex w-64 shrink-0 flex-col gap-2 rounded-lg border border-border bg-canvas p-2"
              >
                <div className="flex items-center justify-between px-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <span>{KANBAN_LABELS[status]}</span>
                  <span className="tabular-nums">{cards.length}</span>
                </div>
                <div className="flex flex-col gap-2">
                  {cards.map((q) => {
                    const idleDays = daysSince(q.last_activity_at);
                    const stalled = !TERMINAL_STATUSES.includes(q.status) && idleDays > stalledThreshold;
                    return (
                      <div
                        key={q.id}
                        draggable
                        onDragStart={(e) => onDragStart(e, q.id)}
                        className={`hover-lift cursor-grab rounded-lg border bg-surface p-2.5 text-sm shadow-card active:cursor-grabbing ${
                          stalled ? "border-danger/40" : "border-border"
                        }`}
                      >
                        <Link to={`/quotations/${q.id}`} className="font-medium text-primary hover:underline">
                          {q.number}
                        </Link>
                        <p className="text-ink-muted">
                          {q.customer_name} — <Money value={Number(q.grand_total)} />
                        </p>
                        <p className={`mt-1 text-xs ${stalled ? "font-medium text-danger" : "text-ink-muted"}`}>
                          {idleDays}d idle
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <>
          <Card padding="sm" className="flex flex-wrap items-end gap-2">
            <Select
              id="filter-status"
              label="Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All</option>
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
            <Select
              id="filter-owner"
              label="Owner"
              value={ownerFilter}
              onChange={(e) => setOwnerFilter(e.target.value)}
            >
              <option value="">All</option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-muted">From</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-muted">To</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg"
              />
            </label>
          </Card>

          {filtered.length > 0 ? (
            <Card padding="none" className="overflow-x-auto">
              <Table>
                <TableHead>
                  <Th>Number</Th>
                  <Th>Customer</Th>
                  <Th>Tier</Th>
                  <Th>Owner</Th>
                  <Th>Amount</Th>
                  <Th>Margin</Th>
                  <Th>Status</Th>
                  <Th>Age</Th>
                </TableHead>
                {filtered.map((q) => (
                  <tr key={q.id}>
                    <Td>
                      <Link to={`/quotations/${q.id}`} className="font-medium text-primary hover:underline">
                        {q.number}
                      </Link>
                    </Td>
                    <Td>{q.customer_name}</Td>
                    <Td>
                      <Badge tone="accent">{q.tier_name}</Badge>
                    </Td>
                    <Td>{q.owner_name}</Td>
                    <Td className="tabular-nums">
                      <Money value={Number(q.grand_total)} />
                    </Td>
                    <Td>
                      <Percent value={Number(q.margin_pct)} />
                    </Td>
                    <Td>
                      <Badge tone={statusTone(q.status)}>{STATUS_LABELS[q.status]}</Badge>
                    </Td>
                    <Td className="tabular-nums text-ink-muted">{daysSince(q.last_activity_at)}d</Td>
                  </tr>
                ))}
              </Table>
            </Card>
          ) : (
            <EmptyState message="No quotations match these filters." />
          )}
        </>
      )}
    </div>
  );
}
