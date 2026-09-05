import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";
import type { Suggestion } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Money } from "@/components/Money";
import { EmptyState } from "@/components/EmptyState";
import { CloseIcon } from "@/components/icons";
import { useToast } from "@/components/Toast";

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
  const toast = useToast();

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
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Dismiss failed", "risk"),
  });

  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold text-ink-muted">Upsell and Cross-Sell Suggestions</h2>
      {!quotationId ? (
        <EmptyState message="Save a draft to see suggestions based on what's already on the order." />
      ) : !suggestions || suggestions.length === 0 ? (
        <EmptyState message="No suggestions right now — add a product to see relevant accessories." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          {suggestions.map((s) => (
            <Card key={s.product_id} padding="sm" className="hover-lift relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  dismissMutation.mutate(s.product_id);
                }}
                disabled={dismissMutation.isPending}
                aria-label="Dismiss"
                className="absolute right-1.5 top-1.5 rounded p-0.5 text-ink-muted transition-colors hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
              >
                <CloseIcon width={14} height={14} />
              </button>
              <button onClick={() => onAdd(s.product_id)} className="flex w-full flex-col gap-1 text-left text-sm">
                <span className="pr-4 font-medium text-primary">+ {s.product_name}</span>
                {s.is_promoted && <Badge tone="accent">Promoted</Badge>}
                <span className="tabular-nums text-success">
                  Margin +<Money value={Number(s.margin_delta)} />
                </span>
              </button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
