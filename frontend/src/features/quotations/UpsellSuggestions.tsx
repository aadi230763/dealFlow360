import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Suggestion } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Money } from "@/components/Money";
import { EmptyState } from "@/components/EmptyState";

export function UpsellSuggestions({
  quotationId,
  excludeProductIds,
  onAdd,
}: {
  quotationId: string | undefined;
  excludeProductIds: string[];
  onAdd: (productId: string) => void;
}) {
  const qc = useQueryClient();

  const { data: allSuggestions } = useQuery({
    queryKey: ["suggestions", quotationId],
    queryFn: () => api.get<Suggestion[]>(`/quotations/${quotationId}/suggestions`),
    enabled: Boolean(quotationId),
  });
  const suggestions = allSuggestions?.filter((s) => !excludeProductIds.includes(s.product_id));

  const dismissMutation = useMutation({
    mutationFn: (productId: string) =>
      api.post(`/quotations/${quotationId}/suggestions/${productId}/dismiss`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suggestions", quotationId] });
    },
  });

  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold text-ink-muted">Upsell and Cross-Sell Suggestions</h2>
      {!quotationId ? (
        <EmptyState message="Save a draft to see suggestions based on what's already on the order." />
      ) : !suggestions || suggestions.length === 0 ? (
        <EmptyState message="No suggestions right now — add a product to see relevant accessories." />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {suggestions.map((s) => (
            <div key={s.product_id} className="relative rounded-sm border border-border bg-surface p-3 text-sm">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  dismissMutation.mutate(s.product_id);
                }}
                aria-label="Dismiss"
                className="absolute right-1.5 top-1.5 text-ink-muted hover:text-risk"
              >
                ✕
              </button>
              <button onClick={() => onAdd(s.product_id)} className="flex w-full flex-col gap-1 text-left">
                <span className="pr-4 font-medium text-accent">+ {s.product_name}</span>
                {s.is_promoted && <Badge tone="accent">Promoted</Badge>}
                <span className="tabular-nums text-healthy">
                  Margin +<Money value={Number(s.margin_delta)} />
                </span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
