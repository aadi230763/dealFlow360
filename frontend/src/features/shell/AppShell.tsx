import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/Badge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Dropdown, DropdownItem } from "@/components/Dropdown";
import { NotificationBell } from "@/components/NotificationBell";
import { ChevronDownIcon, CloseIcon, MenuIcon } from "@/components/icons";
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

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function AppShell() {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  useEventStream();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors duration-150 ${
      isActive ? "bg-primary-bg text-primary" : "text-ink-muted hover:bg-canvas hover:text-ink"
    }`;

  return (
    <div className="flex h-full min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
        <div className="flex items-center justify-between gap-4 px-4 py-2.5 sm:px-6">
          <div className="flex min-w-0 items-center gap-4">
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-muted hover:bg-canvas hover:text-ink lg:hidden"
            >
              {mobileOpen ? <CloseIcon /> : <MenuIcon />}
            </button>
            <div className="flex shrink-0 items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-white">
                D
              </span>
              <span className="text-sm font-semibold tracking-tight text-ink">DealFlow360</span>
            </div>
            <nav className="hidden items-center gap-0.5 lg:flex">
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.to} to={item.to} className={navLinkClass}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {user && <NotificationBell />}
            <ThemeToggle />
            {user && (
              <Dropdown
                trigger={({ open }) => (
                  <span className="flex items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:bg-canvas">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-bg text-xs font-semibold text-primary">
                      {initials(user.name)}
                    </span>
                    <span className="hidden flex-col items-start leading-tight sm:flex">
                      <span className="text-sm font-medium text-ink">{user.name}</span>
                      <span className="text-xs text-ink-muted">{user.role.replace("_", " ")}</span>
                    </span>
                    <ChevronDownIcon
                      className={`hidden text-ink-muted transition-transform duration-150 sm:block ${open ? "rotate-180" : ""}`}
                    />
                  </span>
                )}
              >
                <div className="px-2.5 py-1.5 sm:hidden">
                  <p className="text-sm font-medium text-ink">{user.name}</p>
                  <Badge tone="accent">{user.role.replace("_", " ")}</Badge>
                </div>
                <DropdownItem onClick={logout} danger>
                  Sign out
                </DropdownItem>
              </Dropdown>
            )}
          </div>
        </div>

        {mobileOpen && (
          <nav className="animate-slide-up flex flex-col gap-0.5 border-t border-border px-4 py-2 lg:hidden">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClass} onClick={() => setMobileOpen(false)}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="flex-1 bg-canvas px-4 py-6 sm:px-6">
        <div className="animate-fade-in-up mx-auto w-full max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
