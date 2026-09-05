import { useState } from "react";
import type { RiskResult } from "@/api/types";
import { Percent } from "@/components/Percent";

export function RiskBreakdownPanel({ risk }: { risk: RiskResult | null }) {
  const [open, setOpen] = useState(false);

  if (!risk) return null;

  return (
    <div className="rounded-sm border border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-ink-muted hover:text-ink"
      >
        <span>Why this score</span>
        <span>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="overflow-x-auto border-t border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-1.5">Line</th>
                <th className="px-3 py-1.5">Ceiling</th>
                <th className="px-3 py-1.5">Given</th>
                <th className="px-3 py-1.5">Overage</th>
                <th className="px-3 py-1.5">Weight</th>
                <th className="px-3 py-1.5">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {risk.breakdown.map((b, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-3 py-1.5">{b.product_name}</td>
                  <td className="px-3 py-1.5 tabular-nums">
                    <Percent value={Number(b.ceiling_pct)} />
                  </td>
                  <td className="px-3 py-1.5 tabular-nums">
                    <Percent value={Number(b.discount_pct)} />
                  </td>
                  <td className="px-3 py-1.5 tabular-nums">
                    {Number(b.overage_pct) > 0 ? `+${Number(b.overage_pct).toFixed(2)}pt` : "0pt"}
                  </td>
                  <td className="px-3 py-1.5 tabular-nums">{(Number(b.weight) * 100).toFixed(0)}%</td>
                  <td className="px-3 py-1.5 tabular-nums font-medium">{Number(b.contribution).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {risk.chain_explanations.length > 0 && (
            <div className="border-t border-border px-3 py-2 text-xs text-ink-muted">
              {risk.chain_explanations.map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
