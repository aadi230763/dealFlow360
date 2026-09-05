export function Percent({ value, digits = 1 }: { value: number; digits?: number }) {
  return <span className="tabular-nums">{value.toFixed(digits)}%</span>;
}
