import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { SystemSetting } from "@/api/types";
import { Table, TableHead, Th, Td } from "@/components/Table";
import { EmptyState } from "@/components/EmptyState";
import { useToast } from "@/components/Toast";

const LABELS: Record<string, string> = {
  stalled_deal_day_threshold: "Stalled deal threshold (days)",
  anomaly_zscore_threshold: "Anomaly z-score threshold",
  currency_symbol: "Currency symbol",
};

export function SettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<SystemSetting[]>("/settings"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) => api.put(`/settings/${key}`, { value }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      toast.push("Setting updated");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold tracking-tight">System settings</h1>

      {isLoading ? null : settings && settings.length > 0 ? (
        <Table>
          <TableHead>
            <Th>Setting</Th>
            <Th>Value</Th>
          </TableHead>
          {settings.map((s) => (
            <tr key={s.key}>
              <Td>{LABELS[s.key] ?? s.key}</Td>
              <Td>
                <input
                  defaultValue={String(s.value)}
                  onBlur={(e) => {
                    const raw = e.target.value;
                    if (raw === String(s.value)) return;
                    const numeric = Number(raw);
                    const value = raw !== "" && !Number.isNaN(numeric) ? numeric : raw;
                    updateMutation.mutate({ key: s.key, value });
                  }}
                  className="w-40 rounded-sm border border-border bg-surface px-2 py-1 text-sm tabular-nums"
                />
              </Td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState message="No settings configured yet." />
      )}
    </div>
  );
}
