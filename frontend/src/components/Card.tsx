import type { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
  padding?: "none" | "sm" | "md";
}

const paddingClasses: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
};

export function Card({ interactive = false, padding = "md", className = "", ...props }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-border bg-surface shadow-card ${paddingClasses[padding]} ${
        interactive ? "hover-lift cursor-pointer" : ""
      } ${className}`}
      {...props}
    />
  );
}
