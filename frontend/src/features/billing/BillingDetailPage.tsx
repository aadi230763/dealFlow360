import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { ProrationPreviewOut, SubscriptionDetailOut } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { SkeletonText } from "@/components/Skeleton";

function ModifySubscriptionModal({
  open,
  onClose,
  schedule,
}: {
  open: boolean;
  onClose: () => void;
  schedule: SubscriptionDetailOut;
}) {
  const queryClient = useQueryClient();
  const [newQty, setNewQty] = useState(String(schedule.qty));
  const [preview, setPreview] = useState<ProrationPreviewOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: () => api.post<ProrationPreviewOut>(`/subscriptions/${schedule.schedule_id}/change`, { new_qty: Number(newQty), preview: true }),
    onSuccess: setPreview,
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });
  const confirmMutation = useMutation({
    mutationFn: () => api.post(`/subscriptions/${schedule.schedule_id}/change`, { new_qty: Number(newQty), preview: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", schedule.schedule_id] });
      setPreview(null);
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });

  return (
    <Modal open={open} onClose={onClose} title="Modify Subscription">
      <div className="flex flex-col gap-3">
        {error && <Callout tone="danger">{error}</Callout>}
        <Input
          label="New quantity"
          type="number"
          min={1}
          value={newQty}
          onChange={(e) => {
            setNewQty(e.target.value);
            setPreview(null);
          }}
        />
        {preview ? (
          <>
            <Callout tone="neutral">{preview.summary}</Callout>
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => { setError(null); confirmMutation.mutate(); }} disabled={confirmMutation.isPending}>
                Confirm change
              </Button>
              <Button variant="ghost" onClick={() => setPreview(null)}>
                Back
              </Button>
            </div>
          </>
        ) : (
          <Button
            variant="secondary"
            onClick={() => { setError(null); previewMutation.mutate(); }}
            disabled={previewMutation.isPending || Number(newQty) === schedule.qty}
          >
            Preview change
          </Button>
        )}
      </div>
    </Modal>
  );
}

export function BillingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [modifyOpen, setModifyOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: schedule, isLoading } = useQuery({
    queryKey: ["subscription", id],
    queryFn: () => api.get<SubscriptionDetailOut>(`/subscriptions/${id}`),
    enabled: Boolean(id),
  });

  const cancel = useMutation({
    mutationFn: () => api.post(`/subscriptions/${id}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", id] });
      queryClient.invalidateQueries({ queryKey: ["subscriptions-list"] });
    },
    onError: (e) => setActionError(e instanceof ApiError ? e.detail : String(e)),
  });

  if (isLoading || !schedule) {
    return <SkeletonText lines={6} />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/subscriptions" className="text-sm text-primary hover:underline">
          ← Subscriptions
        </Link>
        <h1 className="text-xl font-semibold tracking-tight text-ink">
          Billing Detail: {schedule.customer_name} — {schedule.plan_name}
        </h1>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge tone={schedule.status === "ACTIVE" ? "healthy" : schedule.status === "PAUSED" ? "warning" : "risk"}>
          {schedule.status}
        </Badge>
        <Badge tone="accent">Order {schedule.order_number}</Badge>
      </div>

      {actionError && <Callout tone="danger">{actionError}</Callout>}

      <Card padding="none" className="overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-semibold text-ink-muted">One-Time Lines (from originating order)</h2>
        {schedule.one_time_lines.length > 0 ? (
          <Table>
            <TableHead>
              <Th>Product</Th>
              <Th>Qty</Th>
              <Th>Amount</Th>
            </TableHead>
            {schedule.one_time_lines.map((l, i) => (
              <tr key={i}>
                <Td>{l.product_name}</Td>
                <Td className="tabular-nums">{l.qty}</Td>
                <Td className="tabular-nums">{l.amount}</Td>
              </tr>
            ))}
          </Table>
        ) : (
          <p className="p-3 text-sm text-ink-muted">No one-time lines on this order.</p>
        )}
      </Card>

      <Card padding="none" className="overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-semibold text-ink-muted">Recurring Lines</h2>
        <Table>
          <TableHead>
            <Th>Plan</Th>
            <Th>Cycle</Th>
            <Th>Next Bill Date</Th>
            <Th>Amount</Th>
          </TableHead>
          <tr>
            <Td>{schedule.plan_name}</Td>
            <Td>{schedule.interval}</Td>
            <Td className="tabular-nums">{new Date(schedule.next_billing_date).toLocaleDateString()}</Td>
            <Td className="tabular-nums">{schedule.amount}</Td>
          </tr>
        </Table>
      </Card>

      <div className="flex gap-2">
        {schedule.status === "ACTIVE" && (
          <>
            <Button variant="secondary" onClick={() => setModifyOpen(true)}>
              Modify Subscription
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setActionError(null);
                cancel.mutate();
              }}
              disabled={cancel.isPending}
            >
              Cancel Subscription
            </Button>
          </>
        )}
      </div>

      <ModifySubscriptionModal open={modifyOpen} onClose={() => setModifyOpen(false)} schedule={schedule} />
    </div>
  );
}
