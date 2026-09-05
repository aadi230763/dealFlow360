export type StepState = "completed" | "active" | "pending" | "failed";

export interface StepperStep {
  label: string;
  state: StepState;
}

const DOT_CLASS: Record<StepState, string> = {
  completed: "bg-success border-success text-white",
  active: "bg-primary border-primary text-white",
  pending: "bg-surface border-border text-ink-muted",
  failed: "bg-danger border-danger text-white",
};

const LABEL_CLASS: Record<StepState, string> = {
  completed: "text-ink",
  active: "text-ink font-semibold",
  pending: "text-ink-muted",
  failed: "text-danger font-semibold",
};

export function Stepper({ steps }: { steps: StepperStep[] }) {
  return (
    <div className="flex items-center">
      {steps.map((step, i) => (
        <div key={i} className="flex flex-1 items-center last:flex-none">
          <div className="flex flex-col items-center gap-1.5">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full border-2 text-xs font-semibold transition-colors duration-150 ${DOT_CLASS[step.state]}`}
            >
              {step.state === "completed" ? "✓" : i + 1}
            </div>
            <span className={`whitespace-nowrap text-xs ${LABEL_CLASS[step.state]}`}>{step.label}</span>
          </div>
          {i < steps.length - 1 && (
            <div
              className={`mx-2 h-0.5 flex-1 transition-colors duration-150 ${
                step.state === "completed" ? "bg-success" : "bg-border"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
