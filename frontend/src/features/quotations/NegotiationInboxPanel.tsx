import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";
import type { NegotiationRequestOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
import { useToast } from "@/components/Toast";

const TYPE_LABEL: Record<string, string> = {
  COMMENT: "Comment",
  CHANGE_REQUEST: "Delivery date request",
  COUNTER_DISCOUNT: "Counter discount",
};

function statusTone(status: string): "neutral" | "healthy" | "risk" | "warning" {
  if (status === "ACCEPTED") return "healthy";
  if (status === "DECLINED") return "risk";
  if (status === "COUNTERED") return "warning";
  return "neutral";
}

function NegotiationRow({ quotationId, req }: { quotationId: string; req: NegotiationRequestOut }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [responding, setResponding] = useState<"counter" | "decline" | null>(null);
  const [message, setMessage] = useState("");
  const [counterPct, setCounterPct] = useState("");

  const respondMutation = useMutation({
    mutationFn: (body: { action: string; response_message?: string | null; counter_discount_pct?: number | null }) =>
      api.post<NegotiationRequestOut>(`/negotiations/${req.id}/respond`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["negotiations", quotationId] });
      qc.invalidateQueries({ queryKey: ["quotation", quotationId] });
      qc.invalidateQueries({ queryKey: ["quotation-risk", quotationId] });
      toast.push("Response sent");
      setResponding(null);
      setMessage("");
      setCounterPct("");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Couldn't respond", "risk"),
  });

  const pending = req.status === "PENDING";

  return (
    <div className="px-3.5 py-2.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-ink">{TYPE_LABEL[req.type] ?? req.type}</span>
            {req.line_product_name && <span className="text-xs text-ink-muted">on {req.line_product_name}</span>}
            <Badge tone={statusTone(req.status)}>{req.status}</Badge>
          </div>
          <p className="mt-0.5 text-sm text-ink">{req.message}</p>
          {req.proposed_discount_pct && (
            <p className="text-xs text-ink-muted">Proposed: {req.proposed_discount_pct}% off</p>
          )}
          {req.requested_delivery_date && (
            <p className="text-xs text-ink-muted">Requested delivery: {req.requested_delivery_date}</p>
          )}
          <p className="text-xs text-ink-faint">{new Date(req.created_at).toLocaleString()}</p>
          {req.response_message && (
            <p className="mt-1 rounded-md bg-canvas px-2 py-1 text-xs text-ink-muted">
              {req.responder_name ? `${req.responder_name}: ` : ""}
              {req.response_message}
              {req.counter_discount_pct && (
                <span className="ml-1 font-medium text-ink">— countered at {req.counter_discount_pct}% off</span>
              )}
            </p>
          )}
          {req.status === "COUNTERED" && req.counter_discount_pct && (
            <p className="mt-1 text-xs text-ink-muted">
              This counter is now visible to the customer on their portal link.
            </p>
          )}
        </div>
        {pending && (
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <div className="flex gap-1.5">
              <Button
                variant="success"
                onClick={() => respondMutation.mutate({ action: "accept" })}
                disabled={respondMutation.isPending}
              >
                Accept
              </Button>
              <Button variant="secondary" onClick={() => setResponding("counter")} disabled={respondMutation.isPending}>
                Counter
              </Button>
              <Button variant="danger" onClick={() => setResponding("decline")} disabled={respondMutation.isPending}>
                Decline
              </Button>
            </div>
          </div>
        )}
      </div>
      {responding && (
        <div className="mt-2 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            {responding === "counter" && req.type === "COUNTER_DISCOUNT" && (
              <input
                type="number"
                min={0}
                max={100}
                step="0.01"
                autoFocus
                value={counterPct}
                onChange={(e) => setCounterPct(e.target.value)}
                placeholder="Counter %"
                className="w-28 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary"
              />
            )}
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={responding === "counter" ? "Note to the customer…" : "Reason for declining…"}
              className="flex-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary"
            />
            <Button
              variant={responding === "counter" ? "warning" : "danger"}
              disabled={
                !message.trim() ||
                respondMutation.isPending ||
                (responding === "counter" && req.type === "COUNTER_DISCOUNT" && !counterPct)
              }
              onClick={() =>
                respondMutation.mutate({
                  action: responding,
                  response_message: message.trim(),
                  counter_discount_pct:
                    responding === "counter" && counterPct ? Number(counterPct) : null,
                })
              }
            >
              Send
            </Button>
            <Button variant="ghost" onClick={() => setResponding(null)}>
              Cancel
            </Button>
          </div>
          {responding === "counter" && req.type === "COUNTER_DISCOUNT" && (
            <p className="text-xs text-ink-muted">
              This percentage is what the customer will see on their portal link — the note is just context.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function NegotiationInboxPanel({ quotationId }: { quotationId: string }) {
  const { data: negotiations } = useQuery({
    queryKey: ["negotiations", quotationId],
    queryFn: () => api.get<NegotiationRequestOut[]>(`/quotations/${quotationId}/negotiations`),
  });

  if (!negotiations || negotiations.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-ink-muted">Customer negotiation</h2>
      <Card padding="none" className="divide-y divide-border">
        {negotiations.map((req) => (
          <NegotiationRow key={req.id} quotationId={quotationId} req={req} />
        ))}
      </Card>
    </div>
  );
}
