import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Product, StockLevel, Warehouse } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { useToast } from "@/components/Toast";

export function WarehousesPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => api.get<Warehouse[]>("/warehouses"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });
  const { data: stock, isLoading } = useQuery({
    queryKey: ["stock"],
    queryFn: () => api.get<StockLevel[]>("/warehouses/stock"),
  });

  const [form, setForm] = useState({ name: "", code: "", shipping_cost_weight: "1.0" });

  const createWarehouse = useMutation({
    mutationFn: () =>
      api.post<Warehouse>("/warehouses", {
        name: form.name,
        code: form.code,
        shipping_cost_weight: Number(form.shipping_cost_weight),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["warehouses"] });
      setForm({ name: "", code: "", shipping_cost_weight: "1.0" });
      toast.push("Warehouse created");
    },
  });

  const upsertStock = useMutation({
    mutationFn: ({
      warehouseId,
      productId,
      onHand,
      reorderPoint,
    }: {
      warehouseId: string;
      productId: string;
      onHand: number;
      reorderPoint: number;
    }) =>
      api.put(`/warehouses/${warehouseId}/stock/${productId}`, {
        on_hand: onHand,
        reorder_point: reorderPoint,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      toast.push("Stock updated");
    },
  });

  const stockFor = useMemo(() => {
    const map = new Map<string, StockLevel>();
    for (const s of stock ?? []) {
      map.set(`${s.warehouse_id}:${s.product_id}`, s);
    }
    return map;
  }, [stock]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createWarehouse.mutate();
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Warehouses & stock</h1>
        <p className="text-sm text-ink-muted">On-hand quantity per product per warehouse. Editable inline.</p>
      </div>

      {!isLoading && warehouses && products && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border-b border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  Product
                </th>
                {warehouses.map((w) => (
                  <th
                    key={w.id}
                    className="border-b border-l border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted"
                  >
                    {w.name} ({w.code})
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-b border-border">
                  <td className="px-3 py-2 font-medium">{p.name}</td>
                  {warehouses.map((w) => {
                    const existing = stockFor.get(`${w.id}:${p.id}`);
                    return (
                      <td key={w.id} className="border-l border-border px-3 py-2">
                        <input
                          type="number"
                          defaultValue={existing?.on_hand ?? 0}
                          onBlur={(e) => {
                            const value = Number(e.target.value);
                            if (value !== (existing?.on_hand ?? 0)) {
                              upsertStock.mutate({
                                warehouseId: w.id,
                                productId: p.id,
                                onHand: value,
                                reorderPoint: existing?.reorder_point ?? 5,
                              });
                            }
                          }}
                          className="w-20 rounded-sm border border-border bg-surface px-2 py-1 tabular-nums"
                        />
                        {existing && existing.reserved > 0 && (
                          <span className="ml-1 text-xs text-ink-muted">({existing.reserved} reserved)</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-border pt-4">
        <Input
          id="w-name"
          label="New warehouse"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <Input
          id="w-code"
          label="Code"
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
          required
        />
        <Input
          id="w-weight"
          label="Shipping cost weight"
          type="number"
          step="0.1"
          value={form.shipping_cost_weight}
          onChange={(e) => setForm({ ...form, shipping_cost_weight: e.target.value })}
        />
        <Button type="submit" disabled={createWarehouse.isPending}>
          Add warehouse
        </Button>
      </form>
    </div>
  );
}
