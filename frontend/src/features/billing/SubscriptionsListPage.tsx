import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { SubscriptionListItem } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Callout } from "@/components/Callout";
import { SkeletonText } from "@/components/Skeleton";
import { Modal } from "@/components/Modal";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { useAuth } from "@/context/AuthContext";

function NewPlanModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [interval, setInterval] = useState("MONTHLY");
  const [proration, setProration] = useState("DAILY_PRORATE");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post("/subscription-plans", {
        name,
        interval,
        interval_count: 1,
        proration_policy: proration,
        cancellation_policy: "CREDIT_REMAINING",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription-plans"] });
      setName("");
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });

  return (
    <Modal open={open} onClose={onClose} title="New Subscription Plan (Admin)">
      <div className="flex flex-col gap-3">
        {error && <Callout tone="danger">{error}</Callout>}
        <Input label="Plan name" value={name} onChange={(e) => setName(e.target.value)} />
        <Select label="Interval" value={interval} onChange={(e) => setInterval(e.target.value)}>
          <option value="MONTHLY">Monthly</option>
          <option value="QUARTERLY">Quarterly</option>
          <option value="YEARLY">Yearly</option>
        </Select>
        <Select label="Proration policy" value={proration} onChange={(e) => setProration(e.target.value)}>
          <option value="DAILY_PRORATE">Daily prorate</option>
          <option value="FULL_PERIOD">Full period</option>
          <option value="NONE">None</option>
        </Select>
        <Button variant="primary" onClick={() => { setError(null); create.mutate(); }} disabled={!name || create.isPending}>
          Create plan
        </Button>
      </div>
    </Modal>
  );
}

export function SubscriptionsListPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  const {
    data: items,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["subscriptions-list"],
    queryFn: () => api.get<SubscriptionListItem[]>("/subscriptions"),
  });

  const counts = useMemo(() => {
    const list = items ?? [];
    return {
      active: list.filter((i) => i.status === "ACTIVE").length,
      paused: list.filter((i) => i.status === "PAUSED").length,
      cancelled: list.filter((i) => i.status === "CANCELLED").length,
    };
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Subscriptions"
        description="Every recurring plan across every customer, regardless of which order it came from."
      />

      <div className="flex flex-wrap gap-2">
        <Badge tone="healthy">Active: {counts.active}</Badge>
        <Badge tone="warning">Paused: {counts.paused}</Badge>
        <Badge tone="risk">Cancelled: {counts.cancelled}</Badge>
      </div>

      {isLoading ? (
        <SkeletonText lines={4} />
      ) : isError ? (
        <Callout tone="danger">
          Couldn't load subscriptions: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
        </Callout>
      ) : (items ?? []).length > 0 ? (
        <Card padding="none" className="overflow-x-auto">
          <Table>
            <TableHead>
              <Th>Customer</Th>
              <Th>Plan</Th>
              <Th>Cycle</Th>
              <Th>Next Bill</Th>
              <Th>Status</Th>
            </TableHead>
            {(items ?? []).map((item) => (
              <tr key={item.schedule_id}>
                <Td>
                  <Link to={`/subscriptions/${item.schedule_id}`} className="font-medium text-primary hover:underline">
                    {item.customer_name}
                  </Link>
                </Td>
                <Td>{item.plan_name}</Td>
                <Td>{item.interval}</Td>
                <Td className="tabular-nums">{new Date(item.next_billing_date).toLocaleDateString()}</Td>
                <Td>
                  <Badge tone={item.status === "ACTIVE" ? "healthy" : item.status === "PAUSED" ? "warning" : "risk"}>
                    {item.status}
                  </Badge>
                </Td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <EmptyState message="No subscriptions yet. Confirm an order with a recurring line to see one here." />
      )}

      <div>
        <Button variant="secondary" onClick={() => setModalOpen(true)} disabled={!isAdmin} title={isAdmin ? undefined : "Admin only"}>
          + New Plan (Admin)
        </Button>
      </div>

      <NewPlanModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
