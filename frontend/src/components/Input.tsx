import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, id, className = "", ...props }: InputProps) {
  return (
    <label className="flex flex-col gap-1.5 text-sm" htmlFor={id}>
      {label && <span className="font-medium text-ink-muted">{label}</span>}
      <input
        id={id}
        className={`rounded-md border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none transition-colors duration-150 placeholder:text-ink-faint focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg disabled:cursor-not-allowed disabled:opacity-50 ${
          error ? "border-danger" : "border-border"
        } ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-danger">{error}</span>}
    </label>
  );
}
