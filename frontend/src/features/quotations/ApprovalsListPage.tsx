import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "@/api/client";
import type { ApprovalListItem } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
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
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Approvals</h1>
        <p className="text-sm text-ink-muted">
          Every quotation that needed, needs, or is going through discount approval.
        </p>
      </div>

      <div className="flex gap-2">
        <Badge tone="accent">Pending: {counts.pending}</Badge>
        <Badge tone="risk">Returned: {counts.returned}</Badge>
        <Badge tone="healthy">Approved: {counts.approved}</Badge>
      </div>

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : isError ? (
        <p className="rounded-sm border border-risk/30 bg-risk-bg px-3 py-2 text-sm text-risk">
          Couldn't load approvals: {error instanceof ApiError ? `${error.status} ${error.detail}` : String(error)}
        </p>
      ) : filtered.length > 0 ? (
        <>
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
                      className="font-medium text-accent hover:underline"
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
          <p className="rounded-sm border border-yellow-300/50 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
            Click any row to open the full approval detail, risk breakdown and audit trail.
          </p>
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
