import type { QuotationStatus } from "@/api/types";

export const STATUS_ORDER: QuotationStatus[] = [
  "DRAFT",
  "PENDING_APPROVAL",
  "APPROVED",
  "SENT",
  "UNDER_NEGOTIATION",
  "CONFIRMED",
  "FULFILLING",
  "INVOICED",
  "REJECTED",
  "CANCELLED",
];

export const TERMINAL_STATUSES: QuotationStatus[] = ["CONFIRMED", "INVOICED", "REJECTED", "CANCELLED"];

export const STATUS_LABELS: Record<QuotationStatus, string> = {
  DRAFT: "Draft",
  PENDING_APPROVAL: "Pending Approval",
  APPROVED: "Approved",
  SENT: "Sent",
  UNDER_NEGOTIATION: "Under Negotiation",
  CONFIRMED: "Confirmed",
  FULFILLING: "Fulfilling",
  INVOICED: "Invoiced",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
};

export function statusTone(status: QuotationStatus): "neutral" | "healthy" | "risk" | "accent" {
  if (status === "REJECTED" || status === "CANCELLED") return "risk";
  if (status === "APPROVED" || status === "CONFIRMED" || status === "INVOICED") return "healthy";
  if (status === "PENDING_APPROVAL" || status === "UNDER_NEGOTIATION") return "accent";
  return "neutral";
}

export function daysSince(isoDate: string): number {
  const then = new Date(isoDate).getTime();
  const now = Date.now();
  return Math.floor((now - then) / (1000 * 60 * 60 * 24));
}

// The mockup's Quotations List Kanban draws exactly these 5 columns. Later-lifecycle
// statuses (SENT, FULFILLING, INVOICED) fold into the nearest column; REJECTED/CANCELLED
// are closed deals and only appear in the table view, not the board.
export const KANBAN_COLUMNS: QuotationStatus[] = [
  "DRAFT",
  "PENDING_APPROVAL",
  "APPROVED",
  "UNDER_NEGOTIATION",
  "CONFIRMED",
];

export const KANBAN_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  PENDING_APPROVAL: "Pending Approval",
  APPROVED: "Approved",
  UNDER_NEGOTIATION: "Negotiation",
  CONFIRMED: "Confirmed",
};

export function kanbanColumnFor(status: QuotationStatus): QuotationStatus | null {
  switch (status) {
    case "DRAFT":
      return "DRAFT";
    case "PENDING_APPROVAL":
      return "PENDING_APPROVAL";
    case "APPROVED":
      return "APPROVED";
    case "SENT":
    case "UNDER_NEGOTIATION":
      return "UNDER_NEGOTIATION";
    case "CONFIRMED":
    case "FULFILLING":
    case "INVOICED":
      return "CONFIRMED";
    default:
      return null;
  }
}

// Risk band the mockup shows instead of raw numbers: LOW (auto-approve), MEDIUM
// (Manager only), HIGH (Manager + Finance, or any chain reaching Finance).
export type RiskBand = "LOW" | "MEDIUM" | "HIGH";

export function riskBand(requiredRoles: string[]): RiskBand {
  if (requiredRoles.length === 0) return "LOW";
  if (requiredRoles.includes("FINANCE")) return "HIGH";
  return "MEDIUM";
}

export function riskBandTone(band: RiskBand): "neutral" | "healthy" | "risk" | "accent" {
  if (band === "LOW") return "healthy";
  if (band === "MEDIUM") return "accent";
  return "risk";
}
