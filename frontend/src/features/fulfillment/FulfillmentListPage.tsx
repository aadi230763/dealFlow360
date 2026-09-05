import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { Product, StockLevel, Warehouse, FulfillmentListItem } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Callout } from "@/components/Callout";
import { SkeletonText } from "@/components/Skeleton";
import { Input } from "@/components/Input";
import { Button } from "@/components/Button";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/components/Toast";

function StockRow({ stock, warehouseName, productName, isAdmin }: { stock: StockLevel; warehouseName: string; productName: string; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [onHand, setOnHand] = useState(String(stock.on_hand));

  const save = useMutation({
    mutationFn: () =>
      api.put(`/warehouses/${stock.warehouse_id}/stock/${stock.product_id}`, {
        on_hand: Number(onHand),
        reorder_point: stock.reorder_point,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stock-levels"] });
      setEditing(false);
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Stock update failed", "risk"),
  });

  const available = stock.on_hand - stock.reserved;

  return (
    <tr>
      <Td className="font-medium">{warehouseName}</Td>
      <Td>{productName}</Td>
      <Td className="tabular-nums">
        {editing ? (
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={0}
              value={onHand}
              onChange={(e) => setOnHand(e.target.value)}
              className="w-20"
            />
            <Button variant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
              Save
            </Button>
          </div>
        ) : (
          <button
            className="rounded px-1 hover:bg-canvas disabled:cursor-default"
            onClick={() => isAdmin && setEditing(true)}
            disabled={!isAdmin}
            title={isAdmin ? "Click to edit" : undefined}
          >
            {stock.on_hand}
          </button>
        )}
      </Td>
      <Td className="tabular-nums">{stock.reserved}</Td>
      <Td className="tabular-nums font-medium">{available}</Td>
    </tr>
  );
}

export function FulfillmentListPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api.get<Warehouse[]>("/warehouses"),
  });
  const { data: stockLevels, isLoading: stockLoading } = useQuery({
    queryKey: ["stock-levels"],
    queryFn: () => api.get<StockLevel[]>("/warehouses/stock"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });
  const {
    data: orders,
    isLoading: ordersLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["fulfillment-list"],
    queryFn: () => api.get<FulfillmentListItem[]>("/fulfillment"),
  });

  const warehouseName = useMemo(() => {
    const map = new Map((warehouses ?? []).map((w) => [w.id, w.name]));
    return (id: string) => map.get(id) ?? "—";
  }, [warehouses]);
  const productName = useMemo(() => {
    const map = new Map((products ?? []).map((p) => [p.id, p.name]));
    return (id: string) => map.get(id) ?? "—";
  }, [products]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Fulfillment and Stock"
        description="Live stock per warehouse, plus every order that still needs fulfilling."
      />

      <Card padding="none" className="overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-semibold text-ink-muted">Stock</h2>
        {stockLoading ? (
          <div className="p-3">
            <SkeletonText lines={3} />
          </div>
        ) : (stockLevels ?? []).length > 0 ? (
          <Table>
            <TableHead>
              <Th>Warehouse</Th>
              <Th>Product</Th>
              <Th>In Stock</Th>
              <Th>Reserved</Th>
              <Th>Available</Th>
            </TableHead>
            {(stockLevels ?? []).map((s) => (
              <StockRow
                key={s.id}
                stock={s}
                warehouseName={warehouseName(s.warehouse_id)}
                productName={productName(s.product_id)}
                isAdmin={isAdmin}
              />
            ))}
          </Table>
        ) : (
          <div className="p-3">
            <EmptyState message="No stock levels configured yet." />
          </div>
        )}
      </Card>

      <Card padding="none" className="overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-semibold text-ink-muted">Orders Awaiting Fulfillment</h2>
        {ordersLoading ? (
          <div className="p-3">
            <SkeletonText lines={3} />
          </div>
        ) : isError ? (
          <div className="p-3">
            <Callout tone="danger">
              Couldn't load fulfillment orders: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
            </Callout>
          </div>
        ) : (orders ?? []).length > 0 ? (
          <Table>
            <TableHead>
              <Th>Order</Th>
              <Th>Customer</Th>
              <Th>Status</Th>
              <Th>Warehouse</Th>
            </TableHead>
            {(orders ?? []).map((o) => (
              <tr key={o.fulfillment_id}>
                <Td>
                  <Link to={`/fulfillment/${o.fulfillment_id}`} className="font-medium text-primary hover:underline">
                    {o.order_number}
                  </Link>
                </Td>
                <Td>{o.customer_name}</Td>
                <Td>
                  <Badge tone={o.status_label === "Backorder" ? "risk" : o.status_label === "Accepted" ? "healthy" : "warning"}>
                    {o.status_label}
                  </Badge>
                </Td>
                <Td>{o.warehouse_names}</Td>
              </tr>
            ))}
          </Table>
        ) : (
          <div className="p-3">
            <EmptyState message="No orders are awaiting fulfillment. Approve a quotation to see a split planned here." />
          </div>
        )}
      </Card>

      <Callout tone="warning">Click an order row to open its warehouse split detail.</Callout>
    </div>
  );
}
