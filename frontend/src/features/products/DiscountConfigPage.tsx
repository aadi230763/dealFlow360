import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { ApprovalRule, CeilingMatrix, Category, CustomerTier } from "@/api/types";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Section } from "@/components/Section";
import { useToast } from "@/components/Toast";

const cellInputClass =
  "w-20 rounded-md border border-border bg-surface px-2 py-1 text-right tabular-nums text-ink outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg";

export function DiscountConfigPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: tiers } = useQuery({ queryKey: ["tiers"], queryFn: () => api.get<CustomerTier[]>("/tiers") });
  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => api.get<Category[]>("/categories"),
  });
  const { data: matrix } = useQuery({
    queryKey: ["ceiling-matrix"],
    queryFn: () => api.get<CeilingMatrix>("/ceilings/matrix"),
  });
  const { data: rules } = useQuery({
    queryKey: ["approval-rules"],
    queryFn: () => api.get<ApprovalRule[]>("/approval-rules"),
  });

  // Local, editable copies -- nothing is saved until "Save configuration".
  const [tierCeilings, setTierCeilings] = useState<Record<string, string>>({});
  const [categoryCeilings, setCategoryCeilings] = useState<Record<string, string>>({});
  const [matrixCells, setMatrixCells] = useState<Record<string, string>>({});
  const [ruleThresholds, setRuleThresholds] = useState<
    Record<string, { min_blended: string; min_peak: string; min_erosion_amount: string }>
  >({});

  useEffect(() => {
    if (tiers) setTierCeilings(Object.fromEntries(tiers.map((t) => [t.id, t.base_discount_ceiling_pct])));
  }, [tiers]);
  useEffect(() => {
    if (categories)
      setCategoryCeilings(Object.fromEntries(categories.map((c) => [c.id, c.default_discount_ceiling_pct])));
  }, [categories]);
  useEffect(() => {
    if (matrix)
      setMatrixCells(
        Object.fromEntries(matrix.cells.map((c) => [`${c.tier_id}:${c.category_id}`, c.ceiling_pct])),
      );
  }, [matrix]);
  useEffect(() => {
    if (rules)
      setRuleThresholds(
        Object.fromEntries(
          rules.map((r) => [
            r.id,
            {
              min_blended: r.min_blended ?? "",
              min_peak: r.min_peak ?? "",
              min_erosion_amount: r.min_erosion_amount ?? "",
            },
          ]),
        ),
      );
  }, [rules]);

  const orderedTiers = useMemo(() => [...(tiers ?? [])].sort((a, b) => a.rank - b.rank), [tiers]);
  const orderedRules = useMemo(() => [...(rules ?? [])].sort((a, b) => a.sequence - b.sequence), [rules]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const calls: Promise<unknown>[] = [];

      for (const tier of orderedTiers) {
        const value = tierCeilings[tier.id];
        if (value !== undefined && value !== tier.base_discount_ceiling_pct) {
          calls.push(api.put(`/tiers/${tier.id}`, { base_discount_ceiling_pct: Number(value) }));
        }
      }
      for (const cat of categories ?? []) {
        const value = categoryCeilings[cat.id];
        if (value !== undefined && value !== cat.default_discount_ceiling_pct) {
          calls.push(api.put(`/categories/${cat.id}`, { default_discount_ceiling_pct: Number(value) }));
        }
      }
      for (const cell of matrix?.cells ?? []) {
        const key = `${cell.tier_id}:${cell.category_id}`;
        const value = matrixCells[key];
        if (value !== undefined && value !== cell.ceiling_pct) {
          calls.push(
            api.put("/ceilings", {
              tier_id: cell.tier_id,
              category_id: cell.category_id,
              ceiling_pct: Number(value),
            }),
          );
        }
      }
      for (const rule of orderedRules) {
        const local = ruleThresholds[rule.id];
        if (!local) continue;
        const body: Record<string, number | null> = {};
        let changed = false;
        if (local.min_blended !== (rule.min_blended ?? "")) {
          body.min_blended = local.min_blended === "" ? null : Number(local.min_blended);
          changed = true;
        }
        if (local.min_peak !== (rule.min_peak ?? "")) {
          body.min_peak = local.min_peak === "" ? null : Number(local.min_peak);
          changed = true;
        }
        if (local.min_erosion_amount !== (rule.min_erosion_amount ?? "")) {
          body.min_erosion_amount = local.min_erosion_amount === "" ? null : Number(local.min_erosion_amount);
          changed = true;
        }
        if (changed) calls.push(api.put(`/approval-rules/${rule.id}`, body));
      }

      await Promise.all(calls);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tiers"] });
      qc.invalidateQueries({ queryKey: ["categories"] });
      qc.invalidateQueries({ queryKey: ["ceiling-matrix"] });
      qc.invalidateQueries({ queryKey: ["approval-rules"] });
      toast.push("Configuration saved");
    },
    onError: (err) => {
      toast.push(err instanceof ApiError ? err.detail : "Save failed", "risk");
    },
  });

  const managerRule = orderedRules[0];
  const financeRule = orderedRules[1];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Discount tiers and approval chains"
        description="When a quote mixes categories with different ceilings, the system computes a blended risk score and routes to the highest required level. All approvals, rejections and edits are logged with user, timestamp and reason."
        actions={
          <>
            <Link to="/products" className="text-sm text-primary hover:underline">
              ← Back to Products
            </Link>
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : "Save configuration"}
            </Button>
          </>
        }
      />

      <Section title="Tier Discount Ceilings">
        <table className="w-full max-w-sm border-collapse text-sm">
          <tbody>
            {orderedTiers.map((tier) => (
              <tr key={tier.id} className="border-b border-border last:border-0">
                <td className="py-1.5 font-medium text-ink">{tier.name}</td>
                <td className="py-1.5 text-right">
                  <input
                    type="number"
                    step="0.1"
                    value={tierCeilings[tier.id] ?? ""}
                    onChange={(e) => setTierCeilings((s) => ({ ...s, [tier.id]: e.target.value }))}
                    className={cellInputClass}
                  />
                  <span className="ml-1 text-ink-muted">% max</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Category Discount Ceilings">
        <table className="w-full max-w-sm border-collapse text-sm">
          <tbody>
            {(categories ?? []).map((cat) => (
              <tr key={cat.id} className="border-b border-border last:border-0">
                <td className="py-1.5 font-medium text-ink">{cat.name}</td>
                <td className="py-1.5 text-right">
                  <input
                    type="number"
                    step="0.1"
                    value={categoryCeilings[cat.id] ?? ""}
                    onChange={(e) => setCategoryCeilings((s) => ({ ...s, [cat.id]: e.target.value }))}
                    className={cellInputClass}
                  />
                  <span className="ml-1 text-ink-muted">% max</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Approval mapping">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="py-1.5">Discount range</th>
                <th className="py-1.5">Required approval</th>
                <th className="py-1.5">Blended ≥</th>
                <th className="py-1.5">Peak ≥</th>
                <th className="py-1.5">Erosion ≥</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-border">
                <td className="py-1.5 text-ink">Within tier or category limit</td>
                <td className="py-1.5 font-medium text-ink">No approval</td>
                <td className="py-1.5 text-ink-muted" colSpan={3}>
                  —
                </td>
              </tr>
              {managerRule && (
                <tr className="border-t border-border">
                  <td className="py-1.5 text-ink">Over limit, blended risk medium</td>
                  <td className="py-1.5 font-medium text-ink">Sales Manager</td>
                  {(["min_blended", "min_peak", "min_erosion_amount"] as const).map((field) => (
                    <td key={field} className="py-1.5">
                      <input
                        type="number"
                        step="0.1"
                        value={ruleThresholds[managerRule.id]?.[field] ?? ""}
                        onChange={(e) =>
                          setRuleThresholds((s) => ({
                            ...s,
                            [managerRule.id]: { ...s[managerRule.id], [field]: e.target.value },
                          }))
                        }
                        className={`${cellInputClass} text-left`}
                      />
                    </td>
                  ))}
                </tr>
              )}
              {financeRule && (
                <tr className="border-t border-border">
                  <td className="py-1.5 text-ink">Over limit, blended risk high</td>
                  <td className="py-1.5 font-medium text-ink">Sales Manager then Finance</td>
                  {(["min_blended", "min_peak", "min_erosion_amount"] as const).map((field) => (
                    <td key={field} className="py-1.5">
                      <input
                        type="number"
                        step="0.1"
                        value={ruleThresholds[financeRule.id]?.[field] ?? ""}
                        onChange={(e) =>
                          setRuleThresholds((s) => ({
                            ...s,
                            [financeRule.id]: { ...s[financeRule.id], [field]: e.target.value },
                          }))
                        }
                        className={`${cellInputClass} text-left`}
                      />
                    </td>
                  ))}
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Tier × Category ceiling matrix"
        description="A superset of the two blocks above — an explicit override per tier/category pair. Resolution order: this matrix, then the category default, then the tier base."
      >
        {matrix && categories && orderedTiers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="border-b border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    Tier
                  </th>
                  {categories.map((cat) => (
                    <th
                      key={cat.id}
                      className="border-b border-l border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted"
                    >
                      {cat.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orderedTiers.map((tier) => (
                  <tr key={tier.id} className="border-b border-border">
                    <td className="px-3 py-2 font-medium text-ink">{tier.name}</td>
                    {categories.map((cat) => {
                      const key = `${tier.id}:${cat.id}`;
                      return (
                        <td key={cat.id} className="border-l border-border px-3 py-2">
                          <input
                            type="number"
                            step="0.1"
                            value={matrixCells[key] ?? ""}
                            onChange={(e) => setMatrixCells((s) => ({ ...s, [key]: e.target.value }))}
                            className={`${cellInputClass} text-left`}
                          />
                          <span className="ml-1 text-xs text-ink-muted">%</span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
