import type { SelectHTMLAttributes } from "react";
import { ChevronDownIcon } from "@/components/icons";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({ label, id, className = "", children, ...props }: SelectProps) {
  return (
    <label className="flex flex-col gap-1.5 text-sm" htmlFor={id}>
      {label && <span className="font-medium text-ink-muted">{label}</span>}
      <div className="relative">
        <select
          id={id}
          className={`w-full appearance-none rounded-md border border-border bg-surface px-2.5 py-1.5 pr-8 text-sm text-ink outline-none transition-colors duration-150 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
          {...props}
        >
          {children}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
      </div>
    </label>
  );
}
