import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/components/Toast";

const ACTION_LABEL: Record<string, string> = {
  approve: "approved",
  reject: "rejected",
  return_for_revision: "sent back for revision",
};

export function useEventStream(): void {
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();

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

      if (data.type === "notification_created") {
        if (user && data.user_id === user.id) {
          qc.invalidateQueries({ queryKey: ["notifications"] });
        }
        return;
      }

      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["approvals-inbox"] });
      const quotationId = data.quotation_id;
      if (typeof quotationId === "string") {
        qc.invalidateQueries({ queryKey: ["quotation", quotationId] });
        qc.invalidateQueries({ queryKey: ["approvals", quotationId] });
        qc.invalidateQueries({ queryKey: ["quotation-risk", quotationId] });
        qc.invalidateQueries({ queryKey: ["negotiations", quotationId] });
      }

      if (data.type === "approval_acted" && typeof data.action === "string") {
        toast.push(`A quotation was ${ACTION_LABEL[data.action] ?? data.action}`);
      } else if (data.type === "quotation_submitted") {
        toast.push("A quotation was submitted for approval");
      } else if (data.type === "quotation_recomputed") {
        toast.push("A quotation was recomputed");
      } else if (data.type === "negotiation_created") {
        toast.push("A customer submitted a negotiation request");
      } else if (data.type === "negotiation_responded") {
        toast.push("A negotiation request was responded to");
      } else if (data.type === "quotation_reentered_approval") {
        toast.push("A confirmed quotation re-entered approval");
      } else if (data.type === "quotation_confirmed") {
        toast.push("A quotation was confirmed");
      } else if (data.type === "quotation_sent") {
        toast.push("A quotation was sent to the customer");
      }
    };

    return () => source.close();
  }, [qc, toast, user]);
}
