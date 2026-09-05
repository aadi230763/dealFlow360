import { useState, type InputHTMLAttributes } from "react";
import { EyeIcon, EyeOffIcon } from "@/components/icons";

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
  error?: string;
}

export function PasswordInput({ label, error, id, className = "", ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <label className="flex flex-col gap-1.5 text-sm" htmlFor={id}>
      {label && <span className="font-medium text-ink-muted">{label}</span>}
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          className={`w-full rounded-md border bg-surface px-2.5 py-1.5 pr-9 text-sm text-ink outline-none transition-colors duration-150 placeholder:text-ink-faint focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary-bg disabled:cursor-not-allowed disabled:opacity-50 ${
            error ? "border-danger" : "border-border"
          } ${className}`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          tabIndex={-1}
          className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center justify-center rounded p-0.5 text-ink-muted transition-colors hover:text-ink"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
      {error && <span className="text-xs text-danger">{error}</span>}
    </label>
  );
}
