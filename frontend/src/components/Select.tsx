import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({ label, id, className = "", children, ...props }: SelectProps) {
  return (
    <label className="flex flex-col gap-1 text-sm" htmlFor={id}>
      {label && <span className="font-medium text-ink-muted">{label}</span>}
      <select
        id={id}
        className={`rounded-sm border border-border bg-surface px-2.5 py-1.5 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
