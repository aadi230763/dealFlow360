import { PairingsPage } from "@/features/admin/PairingsPage";
import { SettingsPage } from "@/features/admin/SettingsPage";

// The mockup gives product pairings and system settings no drawn screen -- just a small
// secondary panel off the Products screen. Not worth its own design pass.
export function ManagePriceFieldsPanel() {
  return (
    <div className="flex max-h-[70vh] flex-col gap-6 overflow-y-auto">
      <PairingsPage />
      <div className="border-t border-border pt-4">
        <SettingsPage />
      </div>
    </div>
  );
}
