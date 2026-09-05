import type { ReactNode } from "react";

type Tone = "neutral" | "warning" | "danger" | "success";

const toneClasses: Record<Tone, string> = {
  neutral: "border-border bg-canvas text-ink-muted",
  warning: "border-warning/30 bg-warning-bg text-warning",
  danger: "border-danger/30 bg-danger-bg text-danger",
  success: "border-success/30 bg-success-bg text-success",
};

export function Callout({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <p className={`rounded-md border px-3 py-2 text-xs leading-relaxed ${toneClasses[tone]}`}>{children}</p>
  );
}
