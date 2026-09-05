import type { ReactNode } from "react";

type Tone = "neutral" | "healthy" | "risk" | "accent";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-canvas text-ink-muted border-border",
  healthy: "bg-[#e6f3ed] text-healthy border-healthy/30",
  risk: "bg-risk-bg text-risk border-risk/30",
  accent: "bg-[#eaf1f8] text-accent border-accent/30",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-medium ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}
