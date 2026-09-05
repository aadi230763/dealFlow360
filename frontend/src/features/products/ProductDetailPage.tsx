import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { Category, CustomerTier, Product } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Section } from "@/components/Section";
import { Callout } from "@/components/Callout";
import { Money } from "@/components/Money";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";

const RECURRING_OPTIONS = ["MONTHLY", "YEARLY", "WEEKLY"];

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: product } = useQuery({
    queryKey: ["product", id],
    queryFn: () => api.get<Product>(`/products/${id}`),
    enabled: Boolean(id),
  });
  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/categories"),
  });
  const { data: tiers } = useQuery({
    queryKey: ["tiers"],
    queryFn: () => api.get<CustomerTier[]>("/tiers"),
  });

  const [form, setForm] = useState<Partial<Product>>({});
  const [variantForm, setVariantForm] = useState({ attribute_name: "", value: "", price_delta: "0" });

  useEffect(() => {
    if (product) setForm(product);
  }, [product]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put(`/products/${id}`, {
        name: form.name,
        category_id: form.category_id,
        list_price: Number(form.list_price),
        unit: form.unit,
        description: form.description,
        tax_pct: Number(form.tax_pct),
        is_subscription: form.is_subscription,
        recurring_interval: form.is_subscription ? form.recurring_interval : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product", id] });
      qc.invalidateQueries({ queryKey: ["products"] });
      toast.push("Product saved");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Save failed", "risk"),
  });

  const addVariantMutation = useMutation({
    mutationFn: () =>
      api.post(`/products/${id}/variants`, {
        attribute_name: variantForm.attribute_name,
        value: variantForm.value,
        price_delta: Number(variantForm.price_delta),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["product", id] });
      setVariantForm({ attribute_name: "", value: "", price_delta: "0" });
      toast.push("Variant added");
    },
  });

  if (!product) return null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <Link to="/products" className="text-sm text-primary hover:underline">
            ← Products
          </Link>
          <h1 className="text-xl font-semibold tracking-tight text-ink">{product.name}</h1>
        </div>
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>

      <Section title="General info">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-3">
            <Input
              id="pd-name"
              label="Product name"
              value={form.name ?? ""}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Select
              id="pd-category"
              label="Category"
              value={form.category_id ?? ""}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
            >
              {categories?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <Input
              id="pd-price"
              label="Price"
              type="number"
              value={form.list_price ?? ""}
              onChange={(e) => setForm({ ...form, list_price: e.target.value })}
            />
            <Input
              id="pd-unit"
              label="Unit"
              value={form.unit ?? ""}
              onChange={(e) => setForm({ ...form, unit: e.target.value })}
            />
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-muted">Description</span>
              <textarea
                value={form.description ?? ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="min-h-[70px] rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg"
              />
            </label>
          </div>
          <div className="flex flex-col gap-3">
            <Input
              id="pd-tax"
              label="Tax %"
              type="number"
              value={form.tax_pct ?? ""}
              onChange={(e) => setForm({ ...form, tax_pct: e.target.value })}
            />
            <div className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-muted">Subscription</span>
              <div className="flex gap-3">
                <label className="flex items-center gap-1.5 text-ink">
                  <input
                    type="radio"
                    checked={form.is_subscription === true}
                    onChange={() => setForm({ ...form, is_subscription: true })}
                  />
                  Yes
                </label>
                <label className="flex items-center gap-1.5 text-ink">
                  <input
                    type="radio"
                    checked={!form.is_subscription}
                    onChange={() => setForm({ ...form, is_subscription: false, recurring_interval: null })}
                  />
                  No
                </label>
              </div>
            </div>
            {form.is_subscription && (
              <Select
                id="pd-recurring"
                label="Recurring"
                value={form.recurring_interval ?? "MONTHLY"}
                onChange={(e) => setForm({ ...form, recurring_interval: e.target.value })}
              >
                {RECURRING_OPTIONS.map((o) => (
                  <option key={o} value={o}>
                    {o.charAt(0) + o.slice(1).toLowerCase()}
                  </option>
                ))}
              </Select>
            )}
            <div>
              <p className="text-sm font-medium text-ink-muted">Quantity on hand</p>
              <p className="text-lg font-semibold tabular-nums text-ink">{product.quantity_on_hand}</p>
            </div>
          </div>
        </div>
      </Section>

      <Section title="Product Variants">
        {product.variants.length > 0 ? (
          <Table>
            <TableHead>
              <Th>Attribute</Th>
              <Th>Value</Th>
              <Th>Extra price</Th>
            </TableHead>
            {product.variants.map((v) => (
              <tr key={v.id}>
                <Td>{v.attribute_name}</Td>
                <Td>{v.value}</Td>
                <Td className="tabular-nums">
                  <Money value={Number(v.price_delta)} />
                </Td>
              </tr>
            ))}
          </Table>
        ) : (
          <EmptyState message="No variants yet." />
        )}
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <Input
            id="v-attr"
            label="Attribute"
            placeholder="Color"
            value={variantForm.attribute_name}
            onChange={(e) => setVariantForm({ ...variantForm, attribute_name: e.target.value })}
          />
          <Input
            id="v-value"
            label="Value"
            placeholder="Blue"
            value={variantForm.value}
            onChange={(e) => setVariantForm({ ...variantForm, value: e.target.value })}
          />
          <Input
            id="v-delta"
            label="Extra price"
            type="number"
            value={variantForm.price_delta}
            onChange={(e) => setVariantForm({ ...variantForm, price_delta: e.target.value })}
          />
          <Button
            variant="secondary"
            onClick={() => addVariantMutation.mutate()}
            disabled={!variantForm.attribute_name || !variantForm.value || addVariantMutation.isPending}
          >
            Add variant
          </Button>
        </div>
      </Section>

      <Section title="Pricelists">
        <Table>
          <TableHead>
            <Th>Tier</Th>
            <Th>Currency</Th>
            <Th>Price Rule</Th>
          </TableHead>
          {(tiers ?? []).map((tier) => (
            <tr key={tier.id}>
              <Td className="font-medium">{tier.name}</Td>
              <Td>INR</Td>
              <Td className="text-ink-muted">
                Base price (<Money value={Number(product.list_price)} />)
              </Td>
            </tr>
          ))}
        </Table>
      </Section>

      <Callout tone="warning">
        Product details should be filled. Recurring orders with this product will be invoiced at the
        beginning of the period.
      </Callout>
    </div>
  );
}
