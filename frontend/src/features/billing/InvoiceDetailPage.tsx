import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { InvoiceDetailOut } from "@/api/types";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { SkeletonText } from "@/components/Skeleton";
import { Stepper, type StepState } from "@/components/Stepper";

const STAGES = ["Order Confirmed", "Shipped", "Invoiced", "Paid"];

function stageStates(stage: string): { label: string; state: StepState }[] {
  const currentIndex = STAGES.indexOf(stage);
  return STAGES.map((label, i) => ({
    label,
    state: i < currentIndex ? "completed" : i === currentIndex ? "active" : "pending",
  }));
}

function RecordPaymentModal({ open, onClose, invoiceId }: { open: boolean; onClose: () => void; invoiceId: string }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("BANK_TRANSFER");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  const record = useMutation({
    mutationFn: () => api.post(`/invoices/${invoiceId}/payments`, { amount: Number(amount), method, reference: reference || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices-list"] });
      setAmount("");
      setReference("");
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });

  return (
    <Modal open={open} onClose={onClose} title="Record Payment">
      <div className="flex flex-col gap-3">
        {error && <Callout tone="danger">{error}</Callout>}
        <Input label="Amount" type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <Input label="Method" value={method} onChange={(e) => setMethod(e.target.value)} />
        <Input label="Reference (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
        <Button variant="primary" onClick={() => { setError(null); record.mutate(); }} disabled={!amount || record.isPending}>
          Record payment
        </Button>
      </div>
    </Modal>
  );
}

function downloadSummary(invoice: InvoiceDetailOut) {
  const lines = [
    `Invoice ${invoice.number}`,
    `Order: ${invoice.order_number}`,
    `Customer: ${invoice.customer_name}`,
    `Type: ${invoice.type}`,
    `Amount: ${invoice.amount}`,
    `Tax: ${invoice.tax}`,
    `Total: ${(Number(invoice.amount) + Number(invoice.tax)).toFixed(2)}`,
    `Status: ${invoice.status}`,
    `Issue date: ${invoice.issue_date}`,
    `Due date: ${invoice.due_date}`,
    invoice.period_start ? `Period: ${invoice.period_start} to ${invoice.period_end}` : "",
    "",
    "Payments:",
    ...invoice.payments.map((p) => `  ${p.received_at} — ${p.amount} via ${p.method}${p.reference ? ` (${p.reference})` : ""}`),
  ].filter(Boolean);

  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${invoice.number}-summary.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [paymentOpen, setPaymentOpen] = useState(false);

  const { data: invoice, isLoading } = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => api.get<InvoiceDetailOut>(`/invoices/${id}`),
    enabled: Boolean(id),
  });

  if (isLoading || !invoice) {
    return <SkeletonText lines={6} />;
  }

  const total = (Number(invoice.amount) + Number(invoice.tax)).toFixed(2);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/invoices" className="text-sm text-primary hover:underline">
          ← Invoices
        </Link>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Invoice Detail: {invoice.number}</h1>
      </div>

      <Stepper steps={stageStates(invoice.stage)} />

      <Card>
        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <p className="text-ink-muted">Customer</p>
            <p className="font-medium text-ink">{invoice.customer_name}</p>
          </div>
          <div>
            <p className="text-ink-muted">Type</p>
            <p className="font-medium text-ink">
              {invoice.number} {invoice.type === "RECURRING" && <span className="text-xs">(Recurring)</span>}
            </p>
          </div>
          <div>
            <p className="text-ink-muted">Total</p>
            <p className="font-medium tabular-nums text-ink">{total}</p>
          </div>
          <div>
            <p className="text-ink-muted">Status</p>
            <Badge tone={invoice.status === "PAID" ? "healthy" : invoice.status === "PARTIAL" ? "warning" : "neutral"}>
              {invoice.status}
            </Badge>
          </div>
        </div>
      </Card>

      {invoice.payments.length > 0 && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold text-ink-muted">Payments</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {invoice.payments.map((p) => (
              <li key={p.id} className="flex justify-between">
                <span>
                  {new Date(p.received_at).toLocaleDateString()} — {p.method}
                  {p.reference ? ` (${p.reference})` : ""}
                </span>
                <span className="tabular-nums font-medium">{p.amount}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Callout tone="warning">Partial invoicing stays reconciled with partial delivery, nothing is billed before it ships.</Callout>

      <div className="flex gap-2">
        {invoice.status !== "PAID" && (
          <Button variant="success" onClick={() => setPaymentOpen(true)}>
            Record Payment
          </Button>
        )}
        <Button variant="secondary" onClick={() => downloadSummary(invoice)}>
          Download Summary
        </Button>
      </div>

      <RecordPaymentModal open={paymentOpen} onClose={() => setPaymentOpen(false)} invoiceId={invoice.id} />
    </div>
  );
}
