import { Children, isValidElement, type ReactNode } from "react";

export function Table({ children }: { children: ReactNode }) {
  // Callers pass <TableHead> as a normal child alongside the body rows (the pattern used
  // everywhere in this codebase), but a <thead> is only valid HTML as a sibling of
  // <tbody>, never nested inside it. Pull it out here so every call site can keep writing
  // <Table><TableHead>...</TableHead>{rows}</Table> unchanged.
  const childArray = Children.toArray(children);
  const head = childArray.find((child) => isValidElement(child) && child.type === TableHead);
  const body = childArray.filter((child) => !(isValidElement(child) && child.type === TableHead));

  return (
    <table className="w-full border-collapse text-sm">
      {head}
      <tbody className="[&>tr]:border-b [&>tr]:border-border [&>tr]:transition-colors [&>tr]:duration-150 [&>tr:hover]:bg-canvas [&>tr:last-child]:border-0">
        {body}
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

export function Td({
  children,
  className = "",
  colSpan,
}: {
  children: ReactNode;
  className?: string;
  colSpan?: number;
}) {
  return (
    <td className={`px-3 py-2.5 ${className}`} colSpan={colSpan}>
      {children}
    </td>
  );
}
