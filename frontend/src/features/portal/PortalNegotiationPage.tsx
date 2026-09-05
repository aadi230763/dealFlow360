import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { portalApi } from "@/api/portalClient";
import type { PortalConfirmOut, PortalQuotationOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Money } from "@/components/Money";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { SkeletonText } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";

const STATUS_CHIP: Record<string, { label: string; tone: "neutral" | "healthy" | "risk" | "accent" | "warning" }> = {
  SENT: { label: "Sent", tone: "accent" },
  UNDER_NEGOTIATION: { label: "Under Negotiation", tone: "warning" },
  PENDING_APPROVAL: { label: "Sent for Internal Review", tone: "warning" },
  CONFIRMED: { label: "Confirmed", tone: "healthy" },
};

export function PortalNegotiationPage() {
  const { token } = useParams<{ token: string }>();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: quotation, isLoading, isError } = useQuery({
    queryKey: ["portal-quotation", token],
    queryFn: () => portalApi.get<PortalQuotationOut>(token!, "/portal/quotation"),
    enabled: Boolean(token),
    retry: false,
  });

  const [lineComments, setLineComments] = useState<Record<string, string>>({});
  const [counterDiscount, setCounterDiscount] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [confirmResult, setConfirmResult] = useState<PortalConfirmOut | null>(null);

  useEffect(() => {
    if (!quotation) return;
    const initial: Record<string, string> = {};
    for (const line of quotation.lines) {
      if (line.comment) initial[line.id] = line.comment;
    }
    setLineComments(initial);
    if (quotation.latest_counter_discount_pct) setCounterDiscount(quotation.latest_counter_discount_pct);
    if (quotation.latest_requested_delivery_date) setDeliveryDate(quotation.latest_requested_delivery_date);
  }, [quotation]);

  const negotiateMutation = useMutation({
    mutationFn: () =>
      portalApi.post<PortalQuotationOut>(token!, "/portal/negotiate", {
        line_comments: lineComments,
        proposed_discount_pct: counterDiscount ? Number(counterDiscount) : null,
        requested_delivery_date: deliveryDate || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portal-quotation", token] });
      toast.push("Request sent to the sales team");
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Couldn't submit request", "risk"),
  });

  const confirmMutation = useMutation({
    mutationFn: () => portalApi.post<PortalConfirmOut>(token!, "/portal/confirm"),
    onSuccess: (result) => {
      setConfirmResult(result);
      qc.invalidateQueries({ queryKey: ["portal-quotation", token] });
      toast.push(result.message);
    },
    onError: (err) => toast.push(err instanceof ApiError ? err.detail : "Couldn't confirm", "risk"),
  });

  const isLocked = quotation ? !["SENT", "UNDER_NEGOTIATION"].includes(quotation.status) : true;

  const chip = useMemo(() => {
    if (!quotation) return null;
    return STATUS_CHIP[quotation.status] ?? { label: quotation.status, tone: "neutral" as const };
  }, [quotation]);

  if (isLoading) {
    return <SkeletonText lines={6} />;
  }

  if (isError || !quotation) {
    return (
      <Callout tone="danger">
        This link is invalid or has expired. Please ask your sales contact for a new one.
      </Callout>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Quotation {quotation.number}</h1>
        <p className="text-sm text-ink-muted">
          Customer reviews and negotiates the quote directly, no email needed.
        </p>
      </div>

      {chip && <Badge tone={chip.tone}>{chip.label}</Badge>}

      {confirmResult && (
        <Callout tone={confirmResult.status === "CONFIRMED" ? "success" : "warning"}>{confirmResult.message}</Callout>
      )}

      <Card padding="none" className="overflow-x-auto">
        <Table>
          <TableHead>
            <Th>Line</Th>
            <Th>Customer Comment</Th>
          </TableHead>
          {quotation.lines.map((line) => (
            <tr key={line.id}>
              <Td>
                <p className="font-medium text-ink">{line.product_name}</p>
                <p className="text-xs text-ink-muted">
                  {line.qty} × <Money value={Number(line.unit_price)} currency={quotation.currency} /> —{" "}
                  <Money value={Number(line.line_total)} currency={quotation.currency} /> total
                </p>
              </Td>
              <Td>
                <input
                  type="text"
                  disabled={isLocked}
                  placeholder="e.g. Can this be 15% off instead of 10%?"
                  value={lineComments[line.id] ?? ""}
                  onChange={(e) => setLineComments((prev) => ({ ...prev, [line.id]: e.target.value }))}
                  className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-60"
                />
              </Td>
            </tr>
          ))}
        </Table>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-ink-muted">Counter Discount %</span>
          <input
            type="number"
            min={0}
            max={100}
            disabled={isLocked}
            value={counterDiscount}
            onChange={(e) => setCounterDiscount(e.target.value)}
            className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-60"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-ink-muted">Requested Delivery Date</span>
          <input
            type="date"
            disabled={isLocked}
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
            className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-60"
          />
        </label>
      </div>

      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface p-4 shadow-card sm:grid-cols-4">
        <div>
          <dt className="text-xs text-ink-muted">Subtotal</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.subtotal)} currency={quotation.currency} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Discount</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.discount_total)} currency={quotation.currency} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Tax</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.tax_total)} currency={quotation.currency} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Total</dt>
          <dd className="tabular-nums font-semibold text-ink">
            <Money value={Number(quotation.grand_total)} currency={quotation.currency} />
          </dd>
        </div>
      </dl>

      <Callout tone="neutral">
        If final terms exceed thresholds, the quote automatically re-enters approval (Screen 6).
      </Callout>

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => negotiateMutation.mutate()}
          disabled={isLocked || negotiateMutation.isPending}
        >
          {negotiateMutation.isPending ? "Sending…" : "Submit Request"}
        </Button>
        <Button
          variant="success"
          onClick={() => confirmMutation.mutate()}
          disabled={isLocked || confirmMutation.isPending}
        >
          {confirmMutation.isPending ? "Confirming…" : "Confirm Quotation"}
        </Button>
      </div>
    </div>
  );
}
