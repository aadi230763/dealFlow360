import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import type { NotificationOut } from "@/api/types";
import { Dropdown } from "@/components/Dropdown";
import { BellIcon } from "@/components/icons";
import { EmptyState } from "@/components/EmptyState";

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function NotificationRow({ notification }: { notification: NotificationOut }) {
  const qc = useQueryClient();
  const markRead = useMutation({
    mutationFn: () => api.post(`/notifications/${notification.id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = notification.read_at === null;
  const content = (
    <div
      className={`flex flex-col gap-0.5 rounded-md px-2.5 py-2 text-sm transition-colors hover:bg-canvas ${
        unread ? "bg-primary-bg/40" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className={unread ? "font-medium text-ink" : "text-ink-muted"}>{notification.message}</p>
        {unread && <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />}
      </div>
      <span className="text-xs text-ink-faint">{timeAgo(notification.created_at)}</span>
    </div>
  );

  const onRowClick = (e: React.MouseEvent) => {
    // Stop the click from bubbling to Dropdown's content wrapper, which closes the
    // whole panel on any click -- marking-as-read should keep it open.
    e.stopPropagation();
    if (unread) markRead.mutate();
  };

  if (notification.quotation_id) {
    return (
      <Link to={`/quotations/${notification.quotation_id}`} onClick={onRowClick}>
        {content}
      </Link>
    );
  }
  return (
    <button type="button" className="w-full text-left" onClick={onRowClick}>
      {content}
    </button>
  );
}

export function NotificationBell() {
  const qc = useQueryClient();
  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<NotificationOut[]>("/notifications"),
    refetchInterval: 60_000,
  });

  const markAllRead = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unreadCount = (notifications ?? []).filter((n) => n.read_at === null).length;

  return (
    <Dropdown
      trigger={() => (
        <span className="relative flex h-8 w-8 items-center justify-center rounded-md text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
          <BellIcon />
          {unreadCount > 0 && (
            <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-none text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </span>
      )}
    >
      <div className="flex items-center justify-between px-2.5 py-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Notifications</span>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              markAllRead.mutate();
            }}
            className="text-xs font-medium text-primary hover:underline"
          >
            Mark all read
          </button>
        )}
      </div>
      <div className="max-h-96 w-80 overflow-y-auto">
        {!notifications || notifications.length === 0 ? (
          <div className="py-4">
            <EmptyState message="No notifications yet." />
          </div>
        ) : (
          notifications.map((n) => <NotificationRow key={n.id} notification={n} />)
        )}
      </div>
    </Dropdown>
  );
}
