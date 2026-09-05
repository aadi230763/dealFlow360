import { Fragment, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { FulfillmentOut, OverrideAllocationIn, StockLevel, SystemSetting, Warehouse } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { SkeletonText } from "@/components/Skeleton";

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function FulfillmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [overrideMode, setOverrideMode] = useState(false);
  const [assignments, setAssignments] = useState<Record<string, Record<string, string>>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: fulfillment, isLoading } = useQuery({
    queryKey: ["fulfillment", id],
    queryFn: () => api.get<FulfillmentOut>(`/fulfillment/${id}`),
    enabled: Boolean(id),
  });
  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api.get<Warehouse[]>("/warehouses"),
  });
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SystemSetting[]>("/settings"),
  });
  const { data: stockLevels } = useQuery({
    queryKey: ["stock-levels"],
    queryFn: () => api.get<StockLevel[]>("/warehouses/stock"),
  });

  const baseShipmentCost = useMemo(() => {
    const setting = (settings ?? []).find((s) => s.key === "fulfillment_base_shipment_cost");
    return setting ? Number(setting.value) : 10;
  }, [settings]);

  const warehouseWeight = useMemo(() => {
    const map = new Map((warehouses ?? []).map((w) => [w.id, Number(w.shipping_cost_weight)]));
    return (id: string) => map.get(id) ?? 1;
  }, [warehouses]);

  const availableAt = useMemo(() => {
    const map = new Map((stockLevels ?? []).map((s) => [`${s.warehouse_id}:${s.product_id}`, s.on_hand - s.reserved]));
    return (warehouseId: string, productId: string) => map.get(`${warehouseId}:${productId}`) ?? 0;
  }, [stockLevels]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["fulfillment", id] });
    queryClient.invalidateQueries({ queryKey: ["fulfillment-list"] });
    queryClient.invalidateQueries({ queryKey: ["stock-levels"] });
  };

  const accept = useMutation({
    mutationFn: () => api.post(`/quotations/${fulfillment?.quotation_id}/fulfillment/accept`),
    onSuccess: invalidate,
    onError: (e) => setActionError(e instanceof ApiError ? e.detail : String(e)),
  });
  const consolidate = useMutation({
    mutationFn: () => api.post(`/fulfillment/${id}/consolidate`),
    onSuccess: invalidate,
    onError: (e) => setActionError(e instanceof ApiError ? e.detail : String(e)),
  });
  const ship = useMutation({
    mutationFn: (allocationId: string) => api.post(`/fulfillment/allocations/${allocationId}/ship`),
    onSuccess: invalidate,
    onError: (e) => setActionError(e instanceof ApiError ? e.detail : String(e)),
  });
  const override = useMutation({
    mutationFn: (allocations: OverrideAllocationIn[]) => api.post(`/fulfillment/${id}/override`, { allocations }),
    onSuccess: () => {
      invalidate();
      setOverrideMode(false);
    },
    onError: (e) => setActionError(e instanceof ApiError ? e.detail : String(e)),
  });

  if (isLoading || !fulfillment) {
    return <SkeletonText lines={6} />;
  }

  const nonBackorder = fulfillment.allocations.filter((a) => !a.is_backorder);
  const backorder = fulfillment.allocations.filter((a) => a.is_backorder);

  const groups = new Map<string, typeof nonBackorder>();
  for (const a of nonBackorder) {
    const key = a.warehouse_id!;
    groups.set(key, [...(groups.get(key) ?? []), a]);
  }

  const uniqueLines = Array.from(
    new Map(fulfillment.allocations.map((a) => [a.quotation_line_id, a])).values(),
  );

  const toggleExpand = (key: string) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const setAssignment = (lineId: string, warehouseId: string, value: string) => {
    setAssignments((prev) => ({ ...prev, [lineId]: { ...prev[lineId], [warehouseId]: value } }));
  };

  const submitOverride = () => {
    const allocations: OverrideAllocationIn[] = [];
    for (const [lineId, byWarehouse] of Object.entries(assignments)) {
      for (const [warehouseId, qtyStr] of Object.entries(byWarehouse)) {
        const qty = Number(qtyStr);
        if (qty > 0) {
          allocations.push({ quotation_line_id: lineId, warehouse_id: warehouseId, qty });
        }
      }
    }
    setActionError(null);
    override.mutate(allocations);
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/fulfillment" className="text-sm text-primary hover:underline">
          ← Fulfillment
        </Link>
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          Fulfillment Detail: {fulfillment.quotation_number} ({fulfillment.customer_name})
        </h1>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge tone={fulfillment.status === "ACCEPTED" ? "healthy" : "warning"}>{fulfillment.status}</Badge>
        {fulfillment.is_manual_override && <Badge tone="accent">Manually overridden</Badge>}
      </div>

      {actionError && <Callout tone="danger">{actionError}</Callout>}

      <Card padding="none" className="overflow-x-auto">
        <Table>
          <TableHead>
            <Th>Warehouse</Th>
            <Th>Qty Fulfilled</Th>
            <Th>Est. Shipments</Th>
            <Th>Cost</Th>
            <Th> </Th>
          </TableHead>
          {Array.from(groups.entries()).map(([warehouseId, allocs]) => {
            const warehouseName = allocs[0].warehouse_name ?? "—";
            const totalQty = allocs.reduce((sum, a) => sum + a.qty, 0);
            const cost = round2(warehouseWeight(warehouseId) * baseShipmentCost);
            return (
              <Fragment key={warehouseId}>
                <tr>
                  <Td className="font-medium">{warehouseName}</Td>
                  <Td className="tabular-nums">{totalQty} units</Td>
                  <Td className="tabular-nums">1</Td>
                  <Td className="tabular-nums">${cost.toFixed(2)}</Td>
                  <Td>
                    <button className="text-xs text-primary hover:underline" onClick={() => toggleExpand(warehouseId)}>
                      {expanded[warehouseId] ? "Hide detail" : "Show detail"}
                    </button>
                  </Td>
                </tr>
                {expanded[warehouseId] && (
                  <tr>
                    <Td colSpan={5}>
                      <div className="flex flex-col gap-1.5 rounded-md bg-canvas p-2.5 text-xs">
                        {allocs.map((a) => (
                          <div key={a.id} className="flex items-center justify-between gap-2">
                            <span>
                              {a.product_name}: {a.qty} of {a.line_qty} units
                              {a.shipped_at ? ` — shipped ${new Date(a.shipped_at).toLocaleDateString()}` : ""}
                            </span>
                            {!a.shipped_at && (
                              <Button variant="secondary" onClick={() => ship.mutate(a.id)} disabled={ship.isPending}>
                                Ship
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    </Td>
                  </tr>
                )}
              </Fragment>
            );
          })}
          {backorder.length > 0 && (
            <tr>
              <Td className="font-medium text-danger">Backorder</Td>
              <Td className="tabular-nums">{backorder.reduce((s, a) => s + a.qty, 0)} units</Td>
              <Td>—</Td>
              <Td>—</Td>
              <Td> </Td>
            </tr>
          )}
        </Table>
      </Card>

      {fulfillment.explanations.length > 0 && (
        <Card padding="sm">
          <h2 className="mb-1.5 text-xs font-semibold text-ink-muted">Why this split</h2>
          <ul className="flex flex-col gap-1 text-xs text-ink-muted">
            {fulfillment.explanations.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Card>
      )}

      {backorder.length > 0 && (
        <Callout tone="warning">
          "Consolidate Remaining Backorder" prompt appears automatically once stock restocks.{" "}
          <button
            className="font-semibold underline"
            onClick={() => {
              setActionError(null);
              consolidate.mutate();
            }}
            disabled={consolidate.isPending}
          >
            Consolidate now
          </button>
        </Callout>
      )}

      {overrideMode && (
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-ink-muted">Manual override</h2>
          <div className="flex flex-col gap-4">
            {uniqueLines.map((line) => {
              const assignedTotal = Object.values(assignments[line.quotation_line_id] ?? {}).reduce(
                (s, v) => s + (Number(v) || 0),
                0,
              );
              return (
                <div key={line.quotation_line_id} className="rounded-md border border-border p-2.5">
                  <p className="mb-2 text-sm font-medium text-ink">
                    {line.product_name} — ordered {line.line_qty}, assigned {assignedTotal}
                    {assignedTotal > line.line_qty && <span className="ml-2 text-danger">exceeds ordered qty</span>}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {(warehouses ?? []).map((w) => {
                      const available = availableAt(w.id, line.product_id);
                      const value = assignments[line.quotation_line_id]?.[w.id] ?? "";
                      return (
                        <div key={w.id} className="flex flex-col gap-1">
                          <span className="text-xs text-ink-muted">
                            {w.name} (avail. {available})
                          </span>
                          <Input
                            type="number"
                            min={0}
                            className="w-24"
                            value={value}
                            onChange={(e) => setAssignment(line.quotation_line_id, w.id, e.target.value)}
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex gap-2">
            <Button variant="primary" onClick={submitOverride} disabled={override.isPending}>
              Submit override
            </Button>
            <Button variant="ghost" onClick={() => setOverrideMode(false)}>
              Cancel
            </Button>
          </div>
        </Card>
      )}

      <div className="flex gap-2">
        {fulfillment.status !== "ACCEPTED" && (
          <Button
            variant="primary"
            onClick={() => {
              setActionError(null);
              accept.mutate();
            }}
            disabled={accept.isPending}
          >
            Accept Suggested Split
          </Button>
        )}
        {fulfillment.status !== "ACCEPTED" && !overrideMode && (
          <Button variant="secondary" onClick={() => setOverrideMode(true)}>
            Manual Override
          </Button>
        )}
      </div>
    </div>
  );
}
