import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { ApprovalListItem } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Callout } from "@/components/Callout";
import { SkeletonText } from "@/components/Skeleton";
import { riskBand, riskBandTone } from "./statusUtils";

export function ApprovalsListPage() {
  const {
    data: items,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["approvals-list"],
    queryFn: () => api.get<ApprovalListItem[]>("/approvals"),
  });
  const [pendingOnly, setPendingOnly] = useState(false);

  const counts = useMemo(() => {
    const list = items ?? [];
    return {
      pending: list.filter((i) => i.overall_status === "PENDING").length,
      returned: list.filter((i) => i.overall_status === "RETURNED").length,
      approved: list.filter((i) => i.overall_status === "APPROVED").length,
    };
  }, [items]);

  const filtered = useMemo(() => {
    if (!pendingOnly) return items ?? [];
    return (items ?? []).filter((i) => i.overall_status === "PENDING");
  }, [items, pendingOnly]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Approvals"
        description="Every quotation that needed, needs, or is going through discount approval."
      />

      <div className="flex flex-wrap gap-2">
        <Badge tone="accent">Pending: {counts.pending}</Badge>
        <Badge tone="risk">Returned: {counts.returned}</Badge>
        <Badge tone="healthy">Approved: {counts.approved}</Badge>
      </div>

      {isLoading ? (
        <SkeletonText lines={4} />
      ) : isError ? (
        <Callout tone="danger">
          Couldn't load approvals: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
        </Callout>
      ) : filtered.length > 0 ? (
        <>
          <Card padding="none" className="overflow-x-auto">
            <Table>
              <TableHead>
                <Th>Quotation</Th>
                <Th>Customer</Th>
                <Th>Blended Risk</Th>
                <Th>Stage</Th>
                <Th>Assigned To</Th>
              </TableHead>
              {filtered.map((item) => {
                const band = riskBand(item.required_roles);
                return (
                  <tr key={item.quotation_id}>
                    <Td>
                      <Link
                        to={`/approvals/${item.quotation_id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {item.quotation_number}
                      </Link>
                    </Td>
                    <Td>{item.customer_name}</Td>
                    <Td>
                      <Badge tone={riskBandTone(band)}>{band}</Badge>
                    </Td>
                    <Td>{item.stage}</Td>
                    <Td>{item.assigned_to}</Td>
                  </tr>
                );
              })}
            </Table>
          </Card>
          <Callout tone="warning">Click any row to open the full approval detail, risk breakdown and audit trail.</Callout>
        </>
      ) : (
        <EmptyState message="Nothing has gone through approval routing yet." />
      )}

      <div>
        <Button variant={pendingOnly ? "primary" : "secondary"} onClick={() => setPendingOnly((v) => !v)}>
          Filter: Pending Only
        </Button>
      </div>
    </div>
  );
}
