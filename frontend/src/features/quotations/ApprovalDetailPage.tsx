import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/api/client";
import type { Customer, CustomerTier, Quotation, RiskResult } from "@/api/types";
import { Badge } from "@/components/Badge";
import { Card } from "@/components/Card";
import { Callout } from "@/components/Callout";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { AuditTrailPanel } from "./AuditTrailPanel";
import { ApprovalChainPanel } from "./ApprovalChainPanel";
import { riskBand, riskBandTone } from "./statusUtils";

export function ApprovalDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: quotation } = useQuery({
    queryKey: ["quotation", id],
    queryFn: () => api.get<Quotation>(`/quotations/${id}`),
    enabled: Boolean(id),
  });
  const { data: risk } = useQuery({
    queryKey: ["quotation-risk", id],
    queryFn: () => api.get<RiskResult>(`/quotations/${id}/risk`),
    enabled: Boolean(id),
  });
  const { data: customers } = useQuery({
    queryKey: ["customers"],
    queryFn: () => api.get<Customer[]>("/customers"),
  });
  const { data: tiers } = useQuery({
    queryKey: ["tiers"],
    queryFn: () => api.get<CustomerTier[]>("/tiers"),
  });

  if (!quotation || !risk) return null;

  const customer = customers?.find((c) => c.id === quotation.customer_id);
  const tier = tiers?.find((t) => t.id === customer?.tier_id);
  const requiredRoles = risk.chain.map((s) => s.required_role);
  const band = riskBand(requiredRoles.length > 0 ? requiredRoles : []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/approvals" className="text-sm text-primary hover:underline">
          ← Approvals
        </Link>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Approval Detail: {quotation.number}</h1>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge tone={riskBandTone(band)}>Blended Risk: {band}</Badge>
        <Badge tone="accent">Customer Tier: {tier?.name ?? "—"}</Badge>
      </div>

      <Card>
        <h2 className="mb-1 text-sm font-semibold text-ink-muted">Why This Quote Was Flagged</h2>
        <div className="overflow-x-auto">
          <Table>
            <TableHead>
              <Th>Line</Th>
              <Th>Discount Given</Th>
              <Th>Limit Allowed</Th>
              <Th>Over By</Th>
              <Th>Weight</Th>
              <Th>Contribution</Th>
            </TableHead>
            {risk.breakdown.map((b, i) => {
              const overage = Number(b.overage_pct);
              return (
                <tr key={i}>
                  <Td className="font-medium">{b.product_name}</Td>
                  <Td className="tabular-nums">{b.discount_pct}%</Td>
                  <Td className="tabular-nums">{b.ceiling_pct}%</Td>
                  <Td className="tabular-nums">
                    {overage > 0 ? (
                      <span className="text-danger">{overage.toFixed(1)}pt OVER</span>
                    ) : (
                      <span className="text-success">0 pt — OK</span>
                    )}
                  </Td>
                  <Td className="tabular-nums">{(Number(b.weight) * 100).toFixed(0)}%</Td>
                  <Td className="tabular-nums font-medium">{Number(b.contribution).toFixed(2)}</Td>
                </tr>
              );
            })}
          </Table>
        </div>
        <div className="mt-3">
          <Callout tone="warning">
            Worst single line ({risk.peak}pt over) plus overall pattern across the order sets the blended
            score. One bad line is enough to require approval.
          </Callout>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink-muted">Approval progress</h2>
        <ApprovalChainPanel
          quotationId={quotation.id}
          ownerUserId={quotation.owner_user_id}
          finalStatus={quotation.status}
        />
      </Card>

      <AuditTrailPanel entityType="quotation" entityId={quotation.id} />
    </div>
  );
}
