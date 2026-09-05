import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/api/client";
import { useToast } from "@/components/Toast";

const ACTION_LABEL: Record<string, string> = {
  approve: "approved",
  reject: "rejected",
  return_for_revision: "sent back for revision",
};

export function useEventStream(): void {
  const qc = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    const source = new EventSource(`/api/events/stream?token=${encodeURIComponent(token)}`);

    source.onmessage = (event) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["approvals-inbox"] });
      const quotationId = data.quotation_id;
      if (typeof quotationId === "string") {
        qc.invalidateQueries({ queryKey: ["quotation", quotationId] });
        qc.invalidateQueries({ queryKey: ["approvals", quotationId] });
        qc.invalidateQueries({ queryKey: ["quotation-risk", quotationId] });
      }

      if (data.type === "approval_acted" && typeof data.action === "string") {
        toast.push(`A quotation was ${ACTION_LABEL[data.action] ?? data.action}`);
      } else if (data.type === "quotation_submitted") {
        toast.push("A quotation was submitted for approval");
      } else if (data.type === "quotation_recomputed") {
        toast.push("A quotation was recomputed");
      }
    };

    return () => source.close();
  }, [qc, toast]);
}
