import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { portalApi } from "@/api/portalClient";
import type { PortalQuotationOut } from "@/api/types";
import { Card } from "@/components/Card";
import { SkeletonText } from "@/components/Skeleton";

export function PortalProfilePage() {
  const { token } = useParams<{ token: string }>();
  const { data: quotation, isLoading } = useQuery({
    queryKey: ["portal-quotation", token],
    queryFn: () => portalApi.get<PortalQuotationOut>(token!, "/portal/quotation"),
    enabled: Boolean(token),
    retry: false,
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight text-ink">Profile</h1>
      {isLoading ? (
        <SkeletonText lines={3} />
      ) : (
        <Card>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">Account</dt>
              <dd className="font-medium text-ink">{quotation?.customer_name ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Currency</dt>
              <dd className="font-medium text-ink">{quotation?.currency ?? "—"}</dd>
            </div>
          </dl>
        </Card>
      )}
    </div>
  );
}
