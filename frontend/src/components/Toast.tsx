import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AlertCircleIcon, CheckCircleIcon, CloseIcon } from "@/components/icons";

interface ToastItem {
  id: number;
  message: string;
  tone: "neutral" | "risk";
}

interface ToastContextValue {
  push: (message: string, tone?: "neutral" | "risk") => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: "neutral" | "risk" = "neutral") => {
      const id = Date.now() + Math.random();
      setItems((prev) => [...prev, { id, message, tone }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={`animate-slide-up flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm shadow-elevated ${
              item.tone === "risk" ? "border-danger/30 bg-danger-bg text-danger" : "border-border bg-surface-elevated text-ink"
            }`}
          >
            {item.tone === "risk" ? (
              <AlertCircleIcon className="mt-0.5 shrink-0" />
            ) : (
              <CheckCircleIcon className="mt-0.5 shrink-0 text-success" />
            )}
            <span className="flex-1">{item.message}</span>
            <button
              onClick={() => dismiss(item.id)}
              aria-label="Dismiss"
              className="shrink-0 rounded p-0.5 text-current opacity-60 transition-opacity hover:opacity-100"
            >
              <CloseIcon width={14} height={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
