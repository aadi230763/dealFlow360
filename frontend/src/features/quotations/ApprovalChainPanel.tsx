import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";
import type { ApprovalRequestOut } from "@/api/types";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { Stepper, type StepState } from "@/components/Stepper";
import { useToast } from "@/components/Toast";

function stepState(status: ApprovalRequestOut["status"]): StepState {
  if (status === "APPROVED") return "completed";
  if (status === "PENDING") return "pending";
  if (status === "REJECTED" || status === "RETURNED") return "failed";
  return "pending"; // CANCELLED -- superseded, rendered as pending/greyed
}

export function ApprovalChainPanel({
  quotationId,
  ownerUserId,
  finalStatus,
}: {
  quotationId: string;
  ownerUserId: string;
  finalStatus: string;
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [commentModal, setCommentModal] = useState<{ id: string; action: "reject" | "return_for_revision" } | null>(
    null,
  );
  const [comment, setComment] = useState("");

  const { data: steps } = useQuery({
    queryKey: ["approvals", quotationId],
    queryFn: () => api.get<ApprovalRequestOut[]>(`/quotations/${quotationId}/approvals`),
  });

  const actMutation = useMutation({
    mutationFn: ({ id, action, comment }: { id: string; action: string; comment?: string }) =>
      api.post(`/approvals/${id}/act`, { action, comment }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals", quotationId] });
      qc.invalidateQueries({ queryKey: ["quotation", quotationId] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
      qc.invalidateQueries({ queryKey: ["approvals-list"] });
      setCommentModal(null);
      setComment("");
      toast.push("Approval updated");
    },
    onError: (err) => {
      toast.push(err instanceof ApiError ? err.detail : "Action failed", "risk");
    },
  });

  if (!steps || steps.length === 0) {
    return <p className="text-sm text-ink-muted">No approval routing was required for this quotation.</p>;
  }

  const earliestPendingSeq = steps
    .filter((s) => s.status === "PENDING")
    .reduce((min, s) => Math.min(min, s.sequence), Infinity);

  const currentStep = steps.find((s) => s.status === "PENDING" && s.sequence === earliestPendingSeq);
  const canAct = Boolean(
    currentStep && user?.role === currentStep.required_role && user?.id !== ownerUserId,
  );

  const stepperSteps = [
    { label: "Submitted", state: "completed" as StepState },
    ...[...steps]
      .sort((a, b) => a.sequence - b.sequence)
      .map((s) => ({ label: s.required_role.replace("_", " "), state: stepState(s.status) })),
    {
      label: "Confirmed",
      state: (finalStatus === "APPROVED" ? "completed" : "pending") as StepState,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Stepper steps={stepperSteps} />

      <div className="flex flex-col gap-2">
        {[...steps]
          .sort((a, b) => a.sequence - b.sequence)
          .map((step) => (
            <div key={step.id} className="rounded-sm border border-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{step.required_role.replace("_", " ")}</span>
                <span className="text-xs text-ink-muted">{step.status}</span>
              </div>
              {step.acted_by_name && (
                <p className="mt-1 text-xs text-ink-muted">
                  {step.acted_by_name} · {step.acted_at ? new Date(step.acted_at).toLocaleString() : ""}
                </p>
              )}
              {step.comment && <p className="mt-1 text-xs text-ink-muted">"{step.comment}"</p>}
            </div>
          ))}
      </div>

      {canAct && currentStep && (
        <div className="flex gap-2 border-t border-border pt-3">
          <Button
            onClick={() => actMutation.mutate({ id: currentStep.id, action: "approve" })}
            disabled={actMutation.isPending}
            className="bg-healthy border-healthy hover:opacity-90"
          >
            Approve
          </Button>
          <Button
            onClick={() => setCommentModal({ id: currentStep.id, action: "return_for_revision" })}
            className="border-amber-500 bg-amber-500 text-white hover:opacity-90"
          >
            Return for Revision
          </Button>
          <Button variant="danger" onClick={() => setCommentModal({ id: currentStep.id, action: "reject" })}>
            Reject
          </Button>
        </div>
      )}

      <Modal
        open={commentModal !== null}
        onClose={() => setCommentModal(null)}
        title={commentModal?.action === "reject" ? "Reject quotation" : "Return for Revision"}
      >
        <div className="flex flex-col gap-3">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment (required)"
            className="min-h-[80px] rounded-sm border border-border bg-surface px-2.5 py-1.5 text-sm"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCommentModal(null)}>
              Cancel
            </Button>
            <Button
              variant={commentModal?.action === "reject" ? "danger" : "secondary"}
              disabled={!comment.trim() || actMutation.isPending}
              onClick={() =>
                commentModal &&
                actMutation.mutate({ id: commentModal.id, action: commentModal.action, comment })
              }
            >
              Confirm
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
