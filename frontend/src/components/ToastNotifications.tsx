import { create } from 'zustand';
import { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
  dismissible?: boolean;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  clearAll: () => void;
}

const generateId = () => `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

export const useToastStore = create<ToastState>(set => ({
  toasts: [],
  addToast: toast =>
    set(state => ({
      toasts: [
        ...state.toasts,
        {
          ...toast,
          id: generateId(),
          duration: toast.duration ?? 5000,
          dismissible: toast.dismissible ?? true,
        },
      ],
    })),
  removeToast: id =>
    set(state => ({
      toasts: state.toasts.filter(t => t.id !== id),
    })),
  clearAll: () => set({ toasts: [] }),
}));

// Convenience functions
export const toast = {
  success: (message: string, duration?: number) => {
    useToastStore.getState().addToast({ message, type: 'success', duration });
  },
  error: (message: string, duration?: number) => {
    useToastStore.getState().addToast({ message, type: 'error', duration: duration ?? 8000 });
  },
  warning: (message: string, duration?: number) => {
    useToastStore.getState().addToast({ message, type: 'warning', duration });
  },
  info: (message: string, duration?: number) => {
    useToastStore.getState().addToast({ message, type: 'info', duration });
  },
};

// Toast icons
const toastIcons: Record<ToastType, React.ReactElement> = {
  success: (
    <svg className="h-5 w-5 text-emerald-500" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3 8l3.5 3.5L13 5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  error: (
    <svg className="h-5 w-5 text-red-500" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  warning: (
    <svg className="h-5 w-5 text-amber-500" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 2L14.5 13H1.5L8 2z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M8 7v3M8 11.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  info: (
    <svg className="h-5 w-5 text-blue-500" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 5v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

// Toast background colors
const toastStyles: Record<ToastType, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  info: 'border-blue-200 bg-blue-50 text-blue-800',
};

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    if (toast.duration && toast.duration > 0) {
      const timer = setTimeout(onDismiss, toast.duration);
      return () => clearTimeout(timer);
    }
  }, [toast.duration, onDismiss]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={`flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg transition-all animate-in slide-in-from-right ${toastStyles[toast.type]}`}
    >
      {toastIcons[toast.type]}
      <span className="text-sm font-medium">{toast.message}</span>
      {toast.dismissible && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="ml-2 rounded p-1 hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M5 5l6 6M11 5l-6 6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
}
