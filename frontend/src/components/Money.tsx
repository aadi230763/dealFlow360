export function Money({ value, currency = "INR" }: { value: number; currency?: string }) {
  const formatted = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);

  return <span className="tabular-nums">{formatted}</span>;
}
