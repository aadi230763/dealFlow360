import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/api/client";
import type { Category, CustomerTier, Product } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Modal } from "@/components/Modal";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Money } from "@/components/Money";
import { Percent } from "@/components/Percent";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";
import { ManagePriceFieldsPanel } from "./ManagePriceFieldsPanel";

export function ProductCatalogPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  const { data: products, isLoading } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });
  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/categories"),
  });
  const { data: tiers } = useQuery({
    queryKey: ["tiers"],
    queryFn: () => api.get<CustomerTier[]>("/tiers"),
  });

  const [newProductOpen, setNewProductOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    sku: "",
    category_id: "",
    list_price: "",
    unit_cost: "",
    tax_pct: "18",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<Product>("/products", {
        name: form.name,
        sku: form.sku,
        category_id: form.category_id,
        unit: "each",
        list_price: Number(form.list_price),
        unit_cost: Number(form.unit_cost),
        tax_pct: Number(form.tax_pct),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      setForm({ name: "", sku: "", category_id: "", list_price: "", unit_cost: "", tax_pct: "18" });
      setNewProductOpen(false);
      toast.push("Product created");
    },
  });

  const categoryName = (id: string) => categories?.find((c) => c.id === id)?.name ?? "—";

  const kpis = useMemo(() => {
    const list = products ?? [];
    const active = list.filter((p) => p.is_active).length;
    const archived = list.length - active;
    const skus = new Set(list.map((p) => p.sku)).size;
    return { active, archived, skus, tierCount: tiers?.length ?? 0 };
  }, [products, tiers]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Product catalog</h1>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setNewProductOpen(true)}>+ New Product</Button>
          <Button variant="secondary" onClick={() => setManageOpen(true)}>
            Manage Price fields
          </Button>
          <Link to="/products/discount-config">
            <Button variant="secondary">Discount & Approval Config</Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-sm border border-border bg-surface p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total Products</p>
          <p className="text-2xl font-semibold tabular-nums">{kpis.active + kpis.archived}</p>
          <p className="text-xs text-ink-muted">
            {kpis.active} active / {kpis.archived} archived
          </p>
        </div>
        <div className="rounded-sm border border-border bg-surface p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Pricelists</p>
          <p className="text-2xl font-semibold tabular-nums">{kpis.tierCount}</p>
          <p className="text-xs text-ink-muted">tiers, INR</p>
        </div>
        <div className="rounded-sm border border-border bg-surface p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">SKUs</p>
          <p className="text-2xl font-semibold tabular-nums">{kpis.skus}</p>
          <p className="text-xs text-ink-muted">across all products</p>
        </div>
      </div>

      {isLoading ? null : products && products.length > 0 ? (
        <>
          <Table>
            <TableHead>
              <Th>Product name</Th>
              <Th>Category</Th>
              <Th>Variants</Th>
              <Th>Price</Th>
              <Th>Unit</Th>
              <Th>Tax</Th>
              <Th>Status</Th>
            </TableHead>
            {products.map((p) => (
              <tr key={p.id} className="cursor-pointer hover:bg-canvas" onClick={() => navigate(`/products/${p.id}`)}>
                <Td className="font-medium">
                  <Link to={`/products/${p.id}`} className="text-accent hover:underline">
                    {p.name}
                  </Link>
                </Td>
                <Td>{categoryName(p.category_id)}</Td>
                <Td className="tabular-nums">{p.variants.length}</Td>
                <Td className="tabular-nums">
                  <Money value={Number(p.list_price)} />
                </Td>
                <Td>{p.unit}</Td>
                <Td>
                  <Percent value={Number(p.tax_pct)} />
                </Td>
                <Td>
                  {p.is_active ? <Badge tone="healthy">Active</Badge> : <Badge>Archived</Badge>}
                  {p.is_promoted && (
                    <Badge tone="accent">
                      <span className="ml-1">Promoted</span>
                    </Badge>
                  )}
                </Td>
              </tr>
            ))}
          </Table>
          <p className="rounded-sm border border-yellow-300/50 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
            Click a product row to open general info, variants and recurring price lists.
          </p>
        </>
      ) : (
        <EmptyState message="No products yet. Add one to get started." />
      )}

      <Modal open={newProductOpen} onClose={() => setNewProductOpen(false)} title="New product">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <Input
            id="p-name"
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            id="p-sku"
            label="SKU"
            value={form.sku}
            onChange={(e) => setForm({ ...form, sku: e.target.value })}
            required
          />
          <Select
            id="p-cat"
            label="Category"
            value={form.category_id}
            onChange={(e) => setForm({ ...form, category_id: e.target.value })}
            required
          >
            <option value="" disabled>
              Select…
            </option>
            {categories?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Input
            id="p-price"
            label="List price"
            type="number"
            value={form.list_price}
            onChange={(e) => setForm({ ...form, list_price: e.target.value })}
            required
          />
          <Input
            id="p-cost"
            label="Unit cost"
            type="number"
            value={form.unit_cost}
            onChange={(e) => setForm({ ...form, unit_cost: e.target.value })}
            required
          />
          <Input
            id="p-tax"
            label="Tax %"
            type="number"
            value={form.tax_pct}
            onChange={(e) => setForm({ ...form, tax_pct: e.target.value })}
          />
          <Button type="submit" disabled={createMutation.isPending} className="mt-2">
            Create product
          </Button>
        </form>
      </Modal>

      <Modal open={manageOpen} onClose={() => setManageOpen(false)} title="Manage Price fields">
        <ManagePriceFieldsPanel />
      </Modal>
    </div>
  );
}
