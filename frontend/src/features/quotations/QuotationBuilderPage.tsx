import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type {
  Category,
  Customer,
  Product,
  Quotation,
  QuotationLineIn,
  QuotationPreview,
} from "@/api/types";
import { Button } from "@/components/Button";
import { Select } from "@/components/Select";
import { Input } from "@/components/Input";
import { Money } from "@/components/Money";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";
import { RiskMeter } from "./RiskMeter";
import { RiskBreakdownPanel } from "./RiskBreakdownPanel";
import { QuotationDetailView } from "./QuotationDetailView";
import { UpsellSuggestions } from "./UpsellSuggestions";

function routingHelperText(pricing: QuotationPreview | null): string {
  if (!pricing) return "";
  const roles = pricing.risk.chain.map((s) => s.required_role);
  if (roles.length === 0) return "Will auto-approve — no approval needed.";
  if (roles.includes("SALES_MANAGER") && roles.includes("FINANCE")) {
    return "Will route to Sales Manager and Finance.";
  }
  if (roles.includes("FINANCE")) return "Will route to Finance.";
  return "Will route to Sales Manager.";
}

export function QuotationBuilderPage() {
  const { id } = useParams<{ id: string }>();
  const isEditing = Boolean(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: existing } = useQuery({
    queryKey: ["quotation", id],
    queryFn: () => api.get<Quotation>(`/quotations/${id}`),
    enabled: isEditing,
  });
  const { data: customers } = useQuery({
    queryKey: ["customers"],
    queryFn: () => api.get<Customer[]>("/customers"),
  });
  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/categories"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });

  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<QuotationLineIn[]>([]);
  const [pricing, setPricing] = useState<QuotationPreview | null>(null);
  const [addProductId, setAddProductId] = useState("");
  const [bulkDiscount, setBulkDiscount] = useState("");
  const [saving, setSaving] = useState<"draft" | "submit" | null>(null);
  const [loadedForId, setLoadedForId] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (existing && existing.id !== loadedForId) {
      setCustomerId(existing.customer_id);
      setLines(
        existing.lines.map((l) => ({
          product_id: l.product_id,
          variant_id: l.variant_id,
          qty: l.qty,
          discount_pct: Number(l.discount_pct),
          line_type: l.line_type,
        })),
      );
      setLoadedForId(existing.id);
    }
  }, [existing, loadedForId]);

  const linesKey = JSON.stringify(lines);

  useEffect(() => {
    if (!customerId || lines.length === 0) {
      setPricing(null);
      return;
    }
    const handle = setTimeout(() => {
      api
        .post<QuotationPreview>("/quotations/preview", { customer_id: customerId, lines })
        .then(setPricing)
        .catch(() => setPricing(null));
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, linesKey]);

  const productById = useMemo(() => {
    const map = new Map<string, Product>();
    for (const p of products ?? []) map.set(p.id, p);
    return map;
  }, [products]);

  const addProduct = (productId: string) => {
    if (!productId) return;
    setLines((prev) => {
      const idx = prev.findIndex((l) => l.product_id === productId && !l.variant_id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], qty: next[idx].qty + 1 };
        return next;
      }
      return [...prev, { product_id: productId, qty: 1, discount_pct: 0, line_type: "ONE_TIME" }];
    });
    setAddProductId("");
  };

  const updateLine = (index: number, patch: Partial<QuotationLineIn>) => {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  };

  const removeLine = (index: number) => {
    setLines((prev) => prev.filter((_, i) => i !== index));
  };

  const applyBulkDiscount = () => {
    const value = Number(bulkDiscount);
    if (Number.isNaN(value)) return;
    setLines((prev) => prev.map((l) => ({ ...l, discount_pct: value })));
  };

  const persistLines = async (): Promise<string> => {
    if (isEditing && id) {
      await api.put(`/quotations/${id}/lines`, { lines });
      return id;
    }
    const created = await api.post<Quotation>("/quotations", { customer_id: customerId, lines });
    return created.id;
  };

  const handleSaveDraft = async () => {
    if (!customerId || lines.length === 0) return;
    setSaving("draft");
    try {
      const quotationId = await persistLines();
      toast.push("Draft saved");
      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["suggestions", quotationId] });
      navigate(`/quotations/${quotationId}`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.detail : "Could not save draft", "risk");
    } finally {
      setSaving(null);
    }
  };

  const handleSubmit = async () => {
    if (!customerId || lines.length === 0) return;
    setSaving("submit");
    try {
      const quotationId = await persistLines();
      const submitted = await api.post<Quotation>(`/quotations/${quotationId}/submit`);
      toast.push(
        submitted.status === "APPROVED" ? "Confirmed — no approval needed" : "Routed for approval",
      );
      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["quotation", quotationId] });
      navigate(`/quotations/${quotationId}`);
    } catch (err) {
      toast.push(err instanceof ApiError ? err.detail : "Could not submit quotation", "risk");
    } finally {
      setSaving(null);
    }
  };

  if (isEditing && existing && existing.status !== "DRAFT") {
    return <QuotationDetailView quotation={existing} />;
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="text-lg font-semibold tracking-tight">
        {isEditing ? `Quotation ${existing?.number ?? ""}` : "New quotation"}
      </h1>

      <div className="flex items-end gap-2">
        <Select
          id="qb-customer"
          label="Customer"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          disabled={isEditing}
        >
          <option value="" disabled>
            Select customer…
          </option>
          {customers?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Select id="qb-pricelist" label="Price List" disabled>
          <option>Standard (by tier)</option>
        </Select>
      </div>

      <div className="flex items-end gap-2 rounded-sm border border-border bg-surface p-3">
        <Select
          id="qb-add-product"
          label="Add a product"
          value={addProductId}
          onChange={(e) => addProduct(e.target.value)}
        >
          <option value="">Select a product…</option>
          {categories?.map((cat) => (
            <optgroup key={cat.id} label={cat.name}>
              {(products ?? [])
                .filter((p) => p.category_id === cat.id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.list_price}
                  </option>
                ))}
            </optgroup>
          ))}
        </Select>
      </div>

      {lines.length === 0 ? (
        <EmptyState message="No lines yet. Add a product above to start pricing." />
      ) : (
        <div className="overflow-x-auto rounded-sm border border-border bg-surface">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">Product</th>
                <th className="px-3 py-2">Qty</th>
                <th className="px-3 py-2">Price</th>
                <th className="px-3 py-2">Discount</th>
                <th className="px-3 py-2">Limit</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => {
                const product = productById.get(line.product_id);
                const priced = pricing?.lines[index];
                const overage = priced ? Number(priced.overage_pct) : 0;
                return (
                  <tr key={index} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 font-medium">{product?.name ?? "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => updateLine(index, { qty: Math.max(1, line.qty - 1) })}
                          className="rounded-sm border border-border px-1.5 text-ink-muted hover:text-ink"
                        >
                          −
                        </button>
                        <span className="w-8 text-center tabular-nums">{line.qty}</span>
                        <button
                          onClick={() => updateLine(index, { qty: line.qty + 1 })}
                          className="rounded-sm border border-border px-1.5 text-ink-muted hover:text-ink"
                        >
                          +
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {product ? <Money value={Number(product.list_price)} /> : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        step="0.1"
                        value={line.discount_pct}
                        onChange={(e) => updateLine(index, { discount_pct: Number(e.target.value) })}
                        className="w-20 rounded-sm border border-border bg-surface px-2 py-1 tabular-nums"
                      />
                    </td>
                    <td className="px-3 py-2 tabular-nums">{priced ? `${priced.ceiling_pct}%` : "—"}</td>
                    <td className="px-3 py-2">
                      {!priced ? (
                        "—"
                      ) : overage > 0 ? (
                        <span className="font-medium text-risk">OVER (+{overage.toFixed(1)}pt)</span>
                      ) : (
                        <span className="font-medium text-healthy">OK</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => removeLine(index)}
                        className="text-ink-muted hover:text-risk"
                        aria-label="Remove line"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="rounded-sm border border-yellow-300/50 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
        Discount is checked against each line's own limit, as soon as it is entered, not only at submit
        time.
      </p>

      {lines.length > 0 && (
        <div className="flex items-end gap-2 border-t border-border pt-3">
          <Input
            id="qb-bulk-discount"
            label="Apply discount % to all lines"
            type="number"
            step="0.1"
            value={bulkDiscount}
            onChange={(e) => setBulkDiscount(e.target.value)}
          />
          <Button variant="secondary" onClick={applyBulkDiscount}>
            Apply
          </Button>
        </div>
      )}

      <UpsellSuggestions
        quotationId={isEditing ? id : undefined}
        excludeProductIds={lines.map((l) => l.product_id)}
        onAdd={addProduct}
      />

      <dl className="grid grid-cols-4 gap-3 rounded-sm border border-border bg-surface p-4 text-sm">
        <div>
          <dt className="text-ink-muted">Subtotal</dt>
          <dd className="tabular-nums font-medium">
            <Money value={pricing ? Number(pricing.subtotal) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Discount</dt>
          <dd className="tabular-nums font-medium">
            <Money value={pricing ? Number(pricing.discount_total) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Tax</dt>
          <dd className="tabular-nums font-medium">
            <Money value={pricing ? Number(pricing.tax_total) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-ink-muted">Total</dt>
          <dd className="tabular-nums font-semibold transition-all duration-300">
            <Money value={pricing ? Number(pricing.grand_total) : 0} />
          </dd>
        </div>
      </dl>

      <RiskMeter risk={pricing?.risk ?? null} />
      <RiskBreakdownPanel risk={pricing?.risk ?? null} />

      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-xs text-ink-muted">{routingHelperText(pricing)}</p>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={handleSaveDraft}
            disabled={saving !== null || !customerId || lines.length === 0}
          >
            {saving === "draft" ? "Saving…" : "Save Draft"}
          </Button>
          <Button onClick={handleSubmit} disabled={saving !== null || !customerId || lines.length === 0}>
            {saving === "submit" ? "Submitting…" : "Submit for Approval"}
          </Button>
        </div>
      </div>
    </div>
  );
}
