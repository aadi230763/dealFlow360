import { useEffect, useRef, useState } from "react";
import type { RiskResult } from "@/api/types";
import { Percent } from "@/components/Percent";
import { Money } from "@/components/Money";

function useFlashOnChange(value: string): boolean {
  const prev = useRef(value);
  const [flashing, setFlashing] = useState(false);

  useEffect(() => {
    if (prev.current !== value) {
      prev.current = value;
      setFlashing(true);
      const handle = setTimeout(() => setFlashing(false), 400);
      return () => clearTimeout(handle);
    }
  }, [value]);

  return flashing;
}

function chainLabel(risk: RiskResult): { label: string; tone: "healthy" | "risk" } {
  if (risk.chain.length === 0) {
    return { label: "Auto-approve — no approval needed", tone: "healthy" };
  }
  const roles = risk.chain.map((s) => s.required_role);
  if (roles.includes("SALES_MANAGER") && roles.includes("FINANCE")) {
    return { label: "Manager + Finance approval required", tone: "risk" };
  }
  if (roles.includes("FINANCE")) {
    return { label: "Finance approval required", tone: "risk" };
  }
  return { label: "Manager approval required", tone: "risk" };
}

export function RiskMeter({ risk }: { risk: RiskResult | null }) {
  const blendedFlash = useFlashOnChange(risk?.blended ?? "0");
  const state = risk ? chainLabel(risk) : { label: "Add lines to see risk", tone: "healthy" as const };

  const borderClass = state.tone === "risk" ? "border-risk" : "border-healthy";
  const bgClass = state.tone === "risk" ? "bg-risk-bg" : "bg-[#e6f3ed]";
  const textClass = state.tone === "risk" ? "text-risk" : "text-healthy";

  return (
    <div className={`rounded-sm border-2 ${borderClass} ${bgClass} p-3`}>
      <p className={`text-xs font-semibold uppercase tracking-wide ${textClass}`}>{state.label}</p>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center">
        <div>
          <p
            className={`text-2xl font-semibold tabular-nums transition-transform duration-300 ${textClass} ${
              blendedFlash ? "scale-110" : "scale-100"
            }`}
          >
            <Percent value={risk ? Number(risk.blended) : 0} />
          </p>
          <p className="text-xs text-ink-muted">Blended</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums">
            <Percent value={risk ? Number(risk.peak) : 0} />
          </p>
          <p className="text-xs text-ink-muted">Peak</p>
        </div>
        <div>
          <p className="text-lg font-semibold tabular-nums">
            <Money value={risk ? Number(risk.erosion) : 0} />
          </p>
          <p className="text-xs text-ink-muted">Erosion</p>
        </div>
      </div>
    </div>
  );
}
