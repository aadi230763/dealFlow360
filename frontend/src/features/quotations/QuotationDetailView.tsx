import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { Customer, Product, Quotation, RiskResult, SendQuotationOut } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Callout } from "@/components/Callout";
import { Modal } from "@/components/Modal";
import { Money } from "@/components/Money";
import { Percent } from "@/components/Percent";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { useToast } from "@/components/Toast";
import { RiskMeter } from "./RiskMeter";
import { NegotiationInboxPanel } from "./NegotiationInboxPanel";
import { STATUS_LABELS, statusTone } from "./statusUtils";

export function QuotationDetailView({ quotation }: { quotation: Quotation }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [portalLink, setPortalLink] = useState<string | null>(null);

  const { data: customers } = useQuery({
    queryKey: ["customers"],
    queryFn: () => api.get<Customer[]>("/customers"),
  });
  const { data: products } = useQuery({
    queryKey: ["products"],
    queryFn: () => api.get<Product[]>("/products"),
  });
  const { data: risk } = useQuery({
    queryKey: ["quotation-risk", quotation.id],
    queryFn: () => api.get<RiskResult>(`/quotations/${quotation.id}/risk`),
  });

  const confirmMutation = useMutation({
    mutationFn: () => api.post<Quotation>(`/quotations/${quotation.id}/confirm`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quotation", quotation.id] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
      toast.push("Order confirmed — recurring lines invoiced, one-time lines invoice on shipment.");
    },
    onError: (err) => {
      toast.push(err instanceof ApiError ? err.detail : "Confirm failed", "risk");
    },
  });

  const sendMutation = useMutation({
    mutationFn: () => api.post<SendQuotationOut>(`/quotations/${quotation.id}/send`),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["quotation", quotation.id] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
      setPortalLink(`${window.location.origin}${result.url}`);
    },
    onError: (err) => {
      toast.push(err instanceof ApiError ? err.detail : "Couldn't send to customer", "risk");
    },
  });

  const recomputeMutation = useMutation({
    mutationFn: () => api.post<Quotation>(`/quotations/${quotation.id}/recompute`),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["quotation", quotation.id] });
      qc.invalidateQueries({ queryKey: ["quotation-risk", quotation.id] });
      qc.invalidateQueries({ queryKey: ["approvals", quotation.id] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["approvals-list"] });
      toast.push(
        updated.status === "PENDING_APPROVAL"
          ? "Recomputed — quotation re-entered approval"
          : "Recomputed — no change in required approval",
      );
    },
    onError: (err) => {
      toast.push(err instanceof ApiError ? err.detail : "Recompute failed", "risk");
    },
  });

  const customer = customers?.find((c) => c.id === quotation.customer_id);
  const productName = (id: string) => products?.find((p) => p.id === id)?.name ?? "—";
  const wentThroughRouting = quotation.status !== "DRAFT";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Quotation {quotation.number}</h1>
          <p className="text-sm text-ink-muted">{customer?.name ?? "—"}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={statusTone(quotation.status)}>{STATUS_LABELS[quotation.status]}</Badge>
          {wentThroughRouting && (
            <Link to={`/approvals/${quotation.id}`}>
              <Button variant="secondary">View Approval Detail</Button>
            </Link>
          )}
          {quotation.status === "APPROVED" && (
            <Button variant="primary" onClick={() => confirmMutation.mutate()} disabled={confirmMutation.isPending}>
              {confirmMutation.isPending ? "Confirming…" : "Confirm Order"}
            </Button>
          )}
          {(quotation.status === "APPROVED" ||
            quotation.status === "SENT" ||
            quotation.status === "UNDER_NEGOTIATION") && (
            <Button variant="secondary" onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending}>
              {sendMutation.isPending ? "Sending…" : "Send to Customer"}
            </Button>
          )}
          {(quotation.status === "APPROVED" || quotation.status === "CONFIRMED" || quotation.status === "FULFILLING") && (
            <Link to="/fulfillment">
              <Button variant="secondary">View Fulfillment</Button>
            </Link>
          )}
          <Button variant="secondary" onClick={() => recomputeMutation.mutate()} disabled={recomputeMutation.isPending}>
            {recomputeMutation.isPending ? "Recomputing…" : "Recompute"}
          </Button>
        </div>
      </div>

      <Card padding="none" className="overflow-x-auto">
        <Table>
          <TableHead>
            <Th>Product</Th>
            <Th>Qty</Th>
            <Th>Price</Th>
            <Th>Discount</Th>
            <Th>Limit</Th>
            <Th>Status</Th>
          </TableHead>
          {quotation.lines.map((line) => {
            const overage = Number(line.computed.overage_pct ?? 0);
            return (
              <tr key={line.id}>
                <Td className="font-medium">{productName(line.product_id)}</Td>
                <Td className="tabular-nums">{line.qty}</Td>
                <Td className="tabular-nums">
                  <Money value={Number(line.unit_price)} />
                </Td>
                <Td>
                  <Percent value={Number(line.discount_pct)} />
                </Td>
                <Td className="tabular-nums">{line.computed.ceiling_pct ? `${line.computed.ceiling_pct}%` : "—"}</Td>
                <Td>
                  {overage > 0 ? (
                    <span className="font-medium text-danger">OVER (+{overage.toFixed(1)}pt)</span>
                  ) : (
                    <span className="font-medium text-success">OK</span>
                  )}
                </Td>
              </tr>
            );
          })}
        </Table>
      </Card>
      <Callout tone="warning">
        Discount is checked against each line's own limit, as soon as it is entered, not only at submit
        time.
      </Callout>

      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface p-4 shadow-card sm:grid-cols-4">
        <div>
          <dt className="text-xs text-ink-muted">Subtotal</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.subtotal)} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Discount</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.discount_total)} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Tax</dt>
          <dd className="tabular-nums font-medium text-ink">
            <Money value={Number(quotation.tax_total)} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Total</dt>
          <dd className="tabular-nums font-semibold text-ink">
            <Money value={Number(quotation.grand_total)} />
          </dd>
        </div>
      </dl>

      <RiskMeter risk={risk ?? null} />

      <NegotiationInboxPanel quotationId={quotation.id} />

      <Modal open={portalLink !== null} onClose={() => setPortalLink(null)} title="Sent to customer">
        <p className="text-sm text-ink-muted">
          Share this link with the customer. Anyone with it can view and negotiate this quotation, no login
          required.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <input
            readOnly
            value={portalLink ?? ""}
            onFocus={(e) => e.currentTarget.select()}
            className="flex-1 rounded-md border border-border bg-canvas px-2.5 py-1.5 text-sm text-ink outline-none"
          />
          <Button
            variant="secondary"
            onClick={() => {
              if (portalLink) navigator.clipboard.writeText(portalLink);
              toast.push("Link copied");
            }}
          >
            Copy
          </Button>
        </div>
      </Modal>
    </div>
  );
}
