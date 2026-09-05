import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type {
  Category,
  Customer,
  CustomerTier,
  Product,
  Quotation,
  QuotationLineIn,
  QuotationListItem,
  QuotationPreview,
  SubscriptionPlan,
  UserOut,
} from "@/api/types";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/Button";
import { Select } from "@/components/Select";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";
import { Money } from "@/components/Money";
import { Card } from "@/components/Card";
import { Callout } from "@/components/Callout";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";
import { RiskMeter } from "./RiskMeter";
import { RiskBreakdownPanel } from "./RiskBreakdownPanel";
import { QuotationDetailView } from "./QuotationDetailView";
import { UpsellSuggestions } from "./UpsellSuggestions";

const TERMINAL_STATUSES = new Set(["CONFIRMED", "INVOICED", "REJECTED", "CANCELLED"]);

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
  const { data: subscriptionPlans } = useQuery({
    queryKey: ["subscription-plans"],
    queryFn: () => api.get<SubscriptionPlan[]>("/subscription-plans"),
  });
  const { data: allQuotations } = useQuery({
    queryKey: ["quotations"],
    queryFn: () => api.get<QuotationListItem[]>("/quotations"),
  });
  const { data: tiers } = useQuery({
    queryKey: ["tiers"],
    queryFn: () => api.get<CustomerTier[]>("/tiers"),
  });
  const { user } = useAuth();
  const canReassignOwner = user?.role === "ADMIN" || user?.role === "SALES_MANAGER";
  const { data: reps } = useQuery({
    queryKey: ["users", "SALES_REP"],
    queryFn: () => api.get<UserOut[]>("/users?role=SALES_REP"),
    enabled: canReassignOwner,
  });

  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<QuotationLineIn[]>([]);
  const [pricing, setPricing] = useState<QuotationPreview | null>(null);
  const [addProductId, setAddProductId] = useState("");
  const [bulkDiscount, setBulkDiscount] = useState("");
  const [saving, setSaving] = useState<"draft" | "submit" | null>(null);
  const [loadedForId, setLoadedForId] = useState<string | undefined>(undefined);
  const [newCustomerOpen, setNewCustomerOpen] = useState(false);
  const [newCustomerForm, setNewCustomerForm] = useState({ name: "", email: "", tier_id: "" });

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
          subscription_plan_id: l.subscription_plan_id,
          start_date: l.start_date,
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
    const product = productById.get(productId);
    setLines((prev) => {
      const idx = prev.findIndex((l) => l.product_id === productId && !l.variant_id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], qty: next[idx].qty + 1 };
        return next;
      }
      if (product?.is_subscription) {
        return [
          ...prev,
          {
            product_id: productId,
            qty: 1,
            discount_pct: 0,
            line_type: "RECURRING",
            subscription_plan_id: subscriptionPlans?.[0]?.id ?? null,
            start_date: new Date().toISOString().slice(0, 10),
          },
        ];
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

  const selectedCustomer = customers?.find((c) => c.id === customerId);

  const reassignOwner = useMutation({
    mutationFn: (ownerUserId: string) =>
      api.put<Customer>(`/customers/${customerId}`, { owner_user_id: ownerUserId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      toast.push("Account owner updated");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Couldn't reassign owner", "risk"),
  });

  const createCustomer = useMutation({
    mutationFn: () =>
      api.post<Customer>("/customers", {
        name: newCustomerForm.name,
        email: newCustomerForm.email,
        tier_id: newCustomerForm.tier_id,
      }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      setCustomerId(created.id);
      setNewCustomerOpen(false);
      setNewCustomerForm({ name: "", email: "", tier_id: "" });
      toast.push(`Customer created — you're the account owner`);
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Couldn't create customer", "risk"),
  });

  // Warning, not a block: any rep can still quote any customer. This just surfaces that
  // someone else already owns or is actively working this account, same spirit as the
  // negotiation/recompute flows -- real data surfaced to a human, not a rule enforced.
  const othersWorkingThisCustomer = useMemo(() => {
    if (!customerId || !allQuotations || !user) return [];
    return allQuotations.filter(
      (q) =>
        q.customer_id === customerId &&
        q.owner_user_id !== user.id &&
        !TERMINAL_STATUSES.has(q.status) &&
        q.id !== existing?.id,
    );
  }, [customerId, allQuotations, user, existing?.id]);

  if (isEditing && existing && existing.status !== "DRAFT") {
    return <QuotationDetailView quotation={existing} />;
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight text-ink">
        {isEditing ? `Quotation ${existing?.number ?? ""}` : "New quotation"}
      </h1>

      <div className="flex flex-wrap items-end gap-2">
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
        {!isEditing && (
          <Button variant="secondary" onClick={() => setNewCustomerOpen(true)}>
            + New Customer
          </Button>
        )}
      </div>

      {selectedCustomer && (
        <div className="flex flex-wrap items-end gap-2 text-sm text-ink-muted">
          <span>
            Account owner:{" "}
            <span className="font-medium text-ink">{selectedCustomer.owner_name ?? "Unassigned"}</span>
          </span>
          {canReassignOwner && (
            <Select
              id="qb-reassign-owner"
              label="Reassign to"
              value={selectedCustomer.owner_user_id ?? ""}
              onChange={(e) => e.target.value && reassignOwner.mutate(e.target.value)}
              disabled={reassignOwner.isPending}
            >
              <option value="" disabled>
                Choose a rep…
              </option>
              {reps?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          )}
        </div>
      )}

      {selectedCustomer &&
        selectedCustomer.owner_user_id &&
        selectedCustomer.owner_user_id !== user?.id && (
          <Callout tone="warning">
            This customer's account owner is <strong>{selectedCustomer.owner_name}</strong>, not you. You can
            still build and submit this quotation, but coordinate with them first.
          </Callout>
        )}

      {othersWorkingThisCustomer.length > 0 && (
        <Callout tone="warning">
          {othersWorkingThisCustomer.length === 1 ? "Another rep" : `${othersWorkingThisCustomer.length} other reps`}{" "}
          already {othersWorkingThisCustomer.length === 1 ? "has" : "have"} an open quotation with this customer:{" "}
          {othersWorkingThisCustomer
            .map((q) => `${q.number} (${q.owner_name}, ₹${Number(q.grand_total).toLocaleString("en-IN")})`)
            .join(", ")}
          . Not blocked — just worth checking you're not both offering different terms.
        </Callout>
      )}

      <Card padding="sm" className="flex items-end gap-2">
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
      </Card>

      {lines.length === 0 ? (
        <EmptyState message="No lines yet. Add a product above to start pricing." />
      ) : (
        <Card padding="none" className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2.5">Product</th>
                <th className="px-3 py-2.5">Qty</th>
                <th className="px-3 py-2.5">Price</th>
                <th className="px-3 py-2.5">Discount</th>
                <th className="px-3 py-2.5">Type</th>
                <th className="px-3 py-2.5">Plan</th>
                <th className="px-3 py-2.5">Start</th>
                <th className="px-3 py-2.5">Limit</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => {
                const product = productById.get(line.product_id);
                const priced = pricing?.lines[index];
                const overage = priced ? Number(priced.overage_pct) : 0;
                return (
                  <tr key={index} className="border-b border-border transition-colors duration-150 last:border-0 hover:bg-canvas">
                    <td className="px-3 py-2.5 font-medium text-ink">{product?.name ?? "—"}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => updateLine(index, { qty: Math.max(1, line.qty - 1) })}
                          className="rounded-md border border-border px-1.5 text-ink-muted transition-colors hover:bg-surface hover:text-ink"
                        >
                          −
                        </button>
                        <span className="w-8 text-center tabular-nums text-ink">{line.qty}</span>
                        <button
                          onClick={() => updateLine(index, { qty: line.qty + 1 })}
                          className="rounded-md border border-border px-1.5 text-ink-muted transition-colors hover:bg-surface hover:text-ink"
                        >
                          +
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-ink">
                      {product ? <Money value={Number(product.list_price)} /> : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        step="0.1"
                        value={line.discount_pct}
                        onChange={(e) => updateLine(index, { discount_pct: Number(e.target.value) })}
                        className="w-20 rounded-md border border-border bg-surface px-2 py-1 tabular-nums text-ink outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg"
                      />
                    </td>
                    <td className="px-3 py-2.5">
                      {product?.is_subscription ? (
                        <select
                          value={line.line_type ?? "RECURRING"}
                          onChange={(e) => updateLine(index, { line_type: e.target.value as "ONE_TIME" | "RECURRING" })}
                          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink outline-none focus-visible:border-primary"
                        >
                          <option value="RECURRING">Recurring</option>
                          <option value="ONE_TIME">One-Time</option>
                        </select>
                      ) : (
                        <span className="text-ink-muted">One-Time</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {product?.is_subscription && line.line_type === "RECURRING" ? (
                        <select
                          value={line.subscription_plan_id ?? ""}
                          onChange={(e) => updateLine(index, { subscription_plan_id: e.target.value || null })}
                          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink outline-none focus-visible:border-primary"
                        >
                          <option value="" disabled>
                            Select plan…
                          </option>
                          {subscriptionPlans?.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {product?.is_subscription && line.line_type === "RECURRING" ? (
                        <input
                          type="date"
                          value={line.start_date ?? ""}
                          onChange={(e) => updateLine(index, { start_date: e.target.value || null })}
                          className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink outline-none focus-visible:border-primary"
                        />
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums text-ink-muted">{priced ? `${priced.ceiling_pct}%` : "—"}</td>
                    <td className="px-3 py-2.5">
                      {!priced ? (
                        "—"
                      ) : overage > 0 ? (
                        <span className="font-medium text-danger">OVER (+{overage.toFixed(1)}pt)</span>
                      ) : (
                        <span className="font-medium text-success">OK</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => removeLine(index)}
                        className="text-ink-muted transition-colors hover:text-danger"
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
        </Card>
      )}
      <Callout tone="warning">
        Discount is checked against each line's own limit, as soon as it is entered, not only at submit
        time.
      </Callout>

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

      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface p-4 shadow-card sm:grid-cols-4">
        <div>
          <dt className="text-xs text-ink-muted">Subtotal</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={pricing ? Number(pricing.subtotal) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Discount</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={pricing ? Number(pricing.discount_total) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Tax</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={pricing ? Number(pricing.tax_total) : 0} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Total</dt>
          <dd className="tabular-nums font-semibold text-ink transition-all duration-300">
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

      <Modal open={newCustomerOpen} onClose={() => setNewCustomerOpen(false)} title="New customer">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createCustomer.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <Input
            id="nc-name"
            label="Name"
            value={newCustomerForm.name}
            onChange={(e) => setNewCustomerForm({ ...newCustomerForm, name: e.target.value })}
            required
          />
          <Input
            id="nc-email"
            label="Email"
            type="email"
            value={newCustomerForm.email}
            onChange={(e) => setNewCustomerForm({ ...newCustomerForm, email: e.target.value })}
            required
          />
          <Select
            id="nc-tier"
            label="Tier"
            value={newCustomerForm.tier_id}
            onChange={(e) => setNewCustomerForm({ ...newCustomerForm, tier_id: e.target.value })}
            required
          >
            <option value="" disabled>
              Select…
            </option>
            {tiers?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
          {user?.role === "SALES_REP" && (
            <p className="text-xs text-ink-muted">You'll automatically become this customer's account owner.</p>
          )}
          <Button type="submit" disabled={createCustomer.isPending} className="mt-2">
            {createCustomer.isPending ? "Creating…" : "Create customer"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}
