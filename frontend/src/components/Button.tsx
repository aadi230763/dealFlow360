import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "success" | "warning";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variantClasses: Record<Variant, string> = {
  primary: "bg-primary text-white border-primary hover:bg-primary-hover hover:border-primary-hover",
  secondary: "bg-surface text-ink border-border hover:bg-canvas",
  danger: "bg-danger text-white border-danger hover:opacity-90",
  ghost: "bg-transparent text-ink-muted border-transparent hover:bg-canvas hover:text-ink",
  success: "bg-success text-white border-success hover:opacity-90",
  warning: "bg-warning text-white border-warning hover:opacity-90",
};

export function Button({ variant = "primary", className = "", disabled, ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      disabled={disabled}
      {...props}
    />
  );
}
