import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, id, className = "", ...props }: InputProps) {
  return (
    <label className="flex flex-col gap-1 text-sm" htmlFor={id}>
      {label && <span className="font-medium text-ink-muted">{label}</span>}
      <input
        id={id}
        className={`rounded-sm border border-border bg-surface px-2.5 py-1.5 text-sm text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-risk">{error}</span>}
    </label>
  );
}
