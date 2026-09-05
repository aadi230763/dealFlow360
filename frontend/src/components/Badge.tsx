import type { ReactNode } from "react";

type Tone = "neutral" | "healthy" | "risk" | "accent" | "warning";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-canvas text-ink-muted border-border",
  healthy: "bg-success-bg text-success border-success/30",
  risk: "bg-danger-bg text-danger border-danger/30",
  accent: "bg-primary-bg text-primary border-primary/30",
  warning: "bg-warning-bg text-warning border-warning/30",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
