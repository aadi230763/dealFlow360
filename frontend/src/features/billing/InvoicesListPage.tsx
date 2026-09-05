import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { InvoiceListItem } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Callout } from "@/components/Callout";
import { SkeletonText } from "@/components/Skeleton";

export function InvoicesListPage() {
  const {
    data: items,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["invoices-list"],
    queryFn: () => api.get<InvoiceListItem[]>("/invoices"),
  });

  const counts = useMemo(() => {
    const list = items ?? [];
    return {
      unpaid: list.filter((i) => i.status === "ISSUED" || i.status === "PARTIAL").length,
      paid: list.filter((i) => i.status === "PAID").length,
    };
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Invoices" description="Every invoice generated from one-time and recurring lines." />

      <div className="flex flex-wrap gap-2">
        <Badge tone="warning">Unpaid: {counts.unpaid}</Badge>
        <Badge tone="healthy">Paid: {counts.paid}</Badge>
      </div>

      {isLoading ? (
        <SkeletonText lines={4} />
      ) : isError ? (
        <Callout tone="danger">
          Couldn't load invoices: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
        </Callout>
      ) : (items ?? []).length > 0 ? (
        <>
          <Card padding="none" className="overflow-x-auto">
            <Table>
              <TableHead>
                <Th>Invoice #</Th>
                <Th>Customer</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
                <Th>Due Date</Th>
              </TableHead>
              {(items ?? []).map((inv) => (
                <tr key={inv.id}>
                  <Td>
                    <Link to={`/invoices/${inv.id}`} className="font-medium text-primary hover:underline">
                      {inv.number}
                      {inv.type === "RECURRING" && <span className="ml-1 text-xs text-ink-muted">(Recurring)</span>}
                    </Link>
                  </Td>
                  <Td>{inv.customer_name}</Td>
                  <Td className="tabular-nums">{(Number(inv.amount) + Number(inv.tax)).toFixed(2)}</Td>
                  <Td>
                    <Badge tone={inv.status === "PAID" ? "healthy" : inv.status === "PARTIAL" ? "warning" : "neutral"}>
                      {inv.status}
                    </Badge>
                  </Td>
                  <Td className="tabular-nums">{new Date(inv.due_date).toLocaleDateString()}</Td>
                </tr>
              ))}
            </Table>
          </Card>
          <Callout tone="warning">Click an invoice row to open its full payment and delivery reconciliation detail.</Callout>
        </>
      ) : (
        <EmptyState message="No invoices yet. Confirm an order and ship a line, or wait for a recurring period to start." />
      )}
    </div>
  );
}
