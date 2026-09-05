import type { ReactNode } from "react";

export function Table({ children }: { children: ReactNode }) {
  return (
    <table className="w-full border-collapse text-sm">
      <tbody className="[&>tr]:border-b [&>tr]:border-border [&>tr]:transition-colors [&>tr]:duration-150 [&>tr:hover]:bg-canvas [&>tr:last-child]:border-0">
        {children}
      </tbody>
    </table>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {children}
      </tr>
    </thead>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return <th className="px-3 py-2.5 font-semibold">{children}</th>;
}

export function Td({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <td className={`px-3 py-2.5 ${className}`}>{children}</td>;
}
