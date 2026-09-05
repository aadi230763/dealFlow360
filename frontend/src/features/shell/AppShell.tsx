import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { useEventStream } from "@/lib/useEventStream";

interface NavItem {
  to: string;
  label: string;
}

// Exact order from the official mockup, on every internal screen.
const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/quotations", label: "Quotations" },
  { to: "/approvals", label: "Approvals" },
  { to: "/fulfillment", label: "Fulfillment" },
  { to: "/subscriptions", label: "Subscriptions" },
  { to: "/invoices", label: "Invoices" },
  { to: "/deal-health", label: "Deal Health" },
  { to: "/reports", label: "Reports" },
  { to: "/products", label: "Products" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  useEventStream();

  return (
    <div className="flex h-full min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <div className="flex items-center gap-6">
          <span className="text-sm font-semibold tracking-tight">DealFlow360</span>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-sm px-2.5 py-1.5 text-sm font-medium transition-colors ${
                    isActive ? "bg-canvas text-ink" : "text-ink-muted hover:text-ink"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-ink-muted">{user.name}</span>
              <Badge tone="accent">{user.role.replace("_", " ")}</Badge>
            </div>
          )}
          <Button variant="ghost" onClick={logout}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="flex-1 bg-canvas p-6">
        <Outlet />
      </main>
    </div>
  );
}
