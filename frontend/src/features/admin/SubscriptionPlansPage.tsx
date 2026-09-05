import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { ProrationPolicy, SubscriptionInterval, SubscriptionPlan } from "@/api/types";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";

const INTERVALS: SubscriptionInterval[] = ["MONTHLY", "QUARTERLY", "YEARLY"];
const PRORATION_POLICIES: ProrationPolicy[] = ["DAILY_PRORATE", "FULL_PERIOD", "NONE"];

export function SubscriptionPlansPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: plans, isLoading } = useQuery({
    queryKey: ["subscription-plans"],
    queryFn: () => api.get<SubscriptionPlan[]>("/subscription-plans"),
  });

  const [form, setForm] = useState({
    name: "",
    interval: "MONTHLY" as SubscriptionInterval,
    proration_policy: "DAILY_PRORATE" as ProrationPolicy,
    cancellation_policy: "CREDIT_REMAINING",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<SubscriptionPlan>("/subscription-plans", { ...form, interval_count: 1 }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscription-plans"] });
      setForm({ name: "", interval: "MONTHLY", proration_policy: "DAILY_PRORATE", cancellation_policy: "CREDIT_REMAINING" });
      toast.push("Plan created");
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMutation.mutate();
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold tracking-tight">Subscription plans</h1>

      {isLoading ? null : plans && plans.length > 0 ? (
        <Table>
          <TableHead>
            <Th>Name</Th>
            <Th>Interval</Th>
            <Th>Proration</Th>
            <Th>Cancellation</Th>
          </TableHead>
          {plans.map((p) => (
            <tr key={p.id}>
              <Td className="font-medium">{p.name}</Td>
              <Td>
                <Badge tone="accent">{p.interval}</Badge>
              </Td>
              <Td>{p.proration_policy}</Td>
              <Td className="text-ink-muted">{p.cancellation_policy}</Td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState message="No subscription plans yet." />
      )}

      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2 border-t border-border pt-4">
        <Input
          id="sp-name"
          label="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <Select
          id="sp-interval"
          label="Interval"
          value={form.interval}
          onChange={(e) => setForm({ ...form, interval: e.target.value as SubscriptionInterval })}
        >
          {INTERVALS.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </Select>
        <Select
          id="sp-proration"
          label="Proration policy"
          value={form.proration_policy}
          onChange={(e) => setForm({ ...form, proration_policy: e.target.value as ProrationPolicy })}
        >
          {PRORATION_POLICIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
        <Input
          id="sp-cancel"
          label="Cancellation policy"
          value={form.cancellation_policy}
          onChange={(e) => setForm({ ...form, cancellation_policy: e.target.value })}
        />
        <Button type="submit" disabled={createMutation.isPending}>
          Add plan
        </Button>
      </form>
    </div>
  );
}
