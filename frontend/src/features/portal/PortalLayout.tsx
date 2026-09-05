import { NavLink, Outlet, useParams } from "react-router-dom";

// Deliberately does NOT reuse AppShell -- no internal nav, no ThemeToggle/user menu tied to
// AuthContext, no sign-out. This is the isolated, restricted view the spec calls for, not
// an internal screen with items hidden.
const NAV_ITEMS = [
  { to: "quotation", label: "My Quotation" },
  { to: "messages", label: "Messages" },
  { to: "profile", label: "Profile" },
];

export function PortalLayout() {
  const { token } = useParams<{ token: string }>();

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
      isActive ? "bg-primary-bg text-primary" : "text-ink-muted hover:bg-canvas hover:text-ink"
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-20 border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-white">
              D
            </span>
            <span className="text-sm font-semibold tracking-tight text-ink">DealFlow360</span>
          </div>
          <nav className="flex items-center gap-0.5">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={`/portal/${token}/${item.to}`} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 px-4 py-6">
        <div className="mx-auto w-full max-w-3xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
