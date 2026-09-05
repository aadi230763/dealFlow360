import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Product, ProductPairing } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Percent } from "@/components/Percent";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";

export function PairingsPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: pairings, isLoading } = useQuery({
    queryKey: ["pairings"],
    queryFn: () => api.get<ProductPairing[]>("/pairings"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });

  const [form, setForm] = useState({
    product_id: "",
    suggested_product_id: "",
    co_purchase_score: "0.5",
    min_margin_pct: "15",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<ProductPairing>("/pairings", {
        product_id: form.product_id,
        suggested_product_id: form.suggested_product_id,
        co_purchase_score: Number(form.co_purchase_score),
        min_margin_pct: Number(form.min_margin_pct),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pairings"] });
      setForm({ product_id: "", suggested_product_id: "", co_purchase_score: "0.5", min_margin_pct: "15" });
      toast.push("Pairing created");
    },
  });

  const productName = (id: string) => products?.find((p) => p.id === id)?.name ?? "—";

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-ink">Product pairings</h1>
        <p className="text-sm text-ink-muted">
          Upsell suggestions ranked by co-purchase score, filtered by a minimum margin floor.
        </p>
      </div>

      {isLoading ? null : pairings && pairings.length > 0 ? (
        <Table>
          <TableHead>
            <Th>Product</Th>
            <Th>Suggests</Th>
            <Th>Co-purchase score</Th>
            <Th>Min margin</Th>
          </TableHead>
          {pairings.map((p) => (
            <tr key={p.id}>
              <Td>{productName(p.product_id)}</Td>
              <Td className="font-medium">{productName(p.suggested_product_id)}</Td>
              <Td className="tabular-nums">{p.co_purchase_score}</Td>
              <Td>
                <Percent value={Number(p.min_margin_pct)} />
              </Td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState message="No product pairings yet." />
      )}

      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2 border-t border-border pt-4">
        <Select
          id="pp-product"
          label="Product"
          value={form.product_id}
          onChange={(e) => setForm({ ...form, product_id: e.target.value })}
          required
        >
          <option value="" disabled>
            Select…
          </option>
          {products?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        <Select
          id="pp-suggested"
          label="Suggests"
          value={form.suggested_product_id}
          onChange={(e) => setForm({ ...form, suggested_product_id: e.target.value })}
          required
        >
          <option value="" disabled>
            Select…
          </option>
          {products?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        <Input
          id="pp-score"
          label="Co-purchase score"
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={form.co_purchase_score}
          onChange={(e) => setForm({ ...form, co_purchase_score: e.target.value })}
        />
        <Input
          id="pp-margin"
          label="Min margin %"
          type="number"
          step="0.1"
          value={form.min_margin_pct}
          onChange={(e) => setForm({ ...form, min_margin_pct: e.target.value })}
        />
        <Button type="submit" disabled={createMutation.isPending}>
          Add pairing
        </Button>
      </form>
    </div>
  );
}
