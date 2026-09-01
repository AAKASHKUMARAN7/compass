"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { cn } from "@/lib/format";

type ToastTone = "success" | "error" | "info";

interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastContextValue {
  notify: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TONE_STYLES: Record<ToastTone, { ring: string; icon: ReactNode }> = {
  success: {
    ring: "border-emerald-200",
    icon: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />,
  },
  error: {
    ring: "border-rose-200",
    icon: <AlertTriangle className="h-4 w-4 text-rose-600" aria-hidden />,
  },
  info: {
    ring: "border-brand-200",
    icon: <Info className="h-4 w-4 text-brand-600" aria-hidden />,
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current, { ...toast, id }]);
      // Errors stay longer: they usually carry an action the user must take.
      setTimeout(() => dismiss(id), toast.tone === "error" ? 8000 : 4500);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-live="polite"
        aria-label="Notifications"
        className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto flex animate-fade-up items-start gap-3 rounded-xl border bg-surface p-3.5 shadow-overlay",
              TONE_STYLES[toast.tone].ring,
            )}
          >
            <div className="mt-0.5 shrink-0">{TONE_STYLES[toast.tone].icon}</div>
            <div className="min-w-0 flex-1 space-y-0.5">
              <p className="text-[13px] font-semibold text-ink">{toast.title}</p>
              {toast.description ? (
                <p className="text-[12px] leading-relaxed text-ink-muted">
                  {toast.description}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="shrink-0 rounded-md p-1 text-ink-subtle transition-colors hover:bg-canvas hover:text-ink"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider.");
  }
  return context;
}
