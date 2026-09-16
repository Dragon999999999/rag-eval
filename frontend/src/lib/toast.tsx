/**
 * Global toast notification system for RAG-Eval.
 *
 * Provides a simple API for showing notifications:
 * - toast.success(message)
 * - toast.error(message)
 * - toast.info(message)
 * - toast.warning(message)
 */
import * as React from "react";
import { cn } from "@/lib/utils/cn";

export type ToastVariant = "default" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

/**
 * Toast provider hook for adding/removing toasts.
 */
export function useToast() {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

/**
 * Simple toast API for use outside React components.
 * This is a programmatic API that queues toasts to be rendered.
 */
interface ToastAPI {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

let toastQueue: Array<Omit<Toast, "id">> = [];
const toastApiRef: { current: ToastAPI | null } = { current: null };

export const toast: ToastAPI = {
  success: (message: string) => {
    toastQueue.push({ message, variant: "success", duration: 4000 });
    toastApiRef.current?.success(message);
  },
  error: (message: string) => {
    toastQueue.push({ message, variant: "error", duration: 6000 });
    toastApiRef.current?.error(message);
  },
  info: (message: string) => {
    toastQueue.push({ message, variant: "default", duration: 4000 });
    toastApiRef.current?.info(message);
  },
  warning: (message: string) => {
    toastQueue.push({ message, variant: "warning", duration: 5000 });
    toastApiRef.current?.warning(message);
  },
};

interface ToastProviderProps {
  children: React.ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const addToast = React.useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).slice(2);
    const newToast = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);

    // Auto-remove after duration
    if (toast.duration !== 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, toast.duration);
    }
  }, []);

  const removeToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Connect programmatic API to provider
  React.useEffect(() => {
    const api: ToastAPI = {
      success: (message) => {
        addToast({ message, variant: "success" });
      },
      error: (message) => {
        addToast({ message, variant: "error" });
      },
      info: (message) => {
        addToast({ message, variant: "default" });
      },
      warning: (message) => {
        addToast({ message, variant: "warning" });
      },
    };
    toastApiRef.current = api;

    // Process any queued toasts
    toastQueue.forEach((t) => {
      addToast(t);
    });
    toastQueue = [];

    return () => {
      toastApiRef.current = null;
    };
  }, [addToast]);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
}

function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => {
          removeToast(toast.id);
        }} />
      ))}
    </div>
  );
}

interface ToastItemProps {
  toast: Toast;
  onClose: () => void;
}

function ToastItem({ toast, onClose }: ToastItemProps) {
  const variantStyles = {
    default: "bg-surface-elevated text-text-primary border-border-default",
    success: "bg-success-bg text-success border-success/20",
    warning: "bg-warning-bg text-warning border-warning/20",
    error: "bg-error-bg text-error border-error/20",
  };

  const icons = {
    default: null,
    success: "✓",
    warning: "!",
    error: "✕",
  };

  return (
    <div
      role="status"
      className={cn(
        "flex min-w-[300px] max-w-md items-center gap-3 rounded-md border px-4 py-3 text-sm shadow-lg",
        variantStyles[toast.variant]
      )}
    >
      {icons[toast.variant] && (
        <span className="flex h-5 w-5 items-center justify-center text-xs font-bold">
          {icons[toast.variant]}
        </span>
      )}
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={onClose}
        className="ml-auto rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-accent"
        aria-label="Close notification"
      >
        <span className="text-lg leading-none">×</span>
      </button>
    </div>
  );
}
