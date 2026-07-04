import { motion, AnimatePresence } from 'framer-motion';
import { create } from 'zustand';
import { useEffect, useCallback } from 'react';
import { cn } from '../../lib/cn';
import { CheckCircle, XCircle, Warning, Info, X, Sparkle } from '@phosphor-icons/react';

export type ToastType = 'success' | 'error' | 'warning' | 'info' | 'loading';

export interface Toast {
  id: string;
  title?: string;
  message: string;
  description?: string;
  type: ToastType;
  duration?: number;
  dismissible?: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
  onDismiss?: () => void;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  updateToast: (id: string, updates: Partial<Omit<Toast, 'id'>>) => void;
  clearAll: () => void;
  pauseToast: (id: string) => void;
  resumeToast: (id: string) => void;
}

const generateId = () => `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  addToast: toast =>
    set(state => ({
      toasts: [
        ...state.toasts,
        {
          ...toast,
          id: generateId(),
          duration: toast.duration ?? 4000,
          dismissible: toast.dismissible ?? true,
        },
      ],
    })),
  removeToast: id => {
    const toast = get().toasts.find(t => t.id === id);
    toast?.onDismiss?.();
    set(state => ({
      toasts: state.toasts.filter(t => t.id !== id),
    }));
  },
  updateToast: (id, updates) =>
    set(state => ({
      toasts: state.toasts.map(t => (t.id === id ? { ...t, ...updates } : t)),
    })),
  clearAll: () => {
    get().toasts.forEach(t => t.onDismiss?.());
    set({ toasts: [] });
  },
  pauseToast: () => {}, // Placeholder for future implementation
  resumeToast: () => {}, // Placeholder for future implementation
}));

// Toast helper functions
export const toast = {
  success: (message: string, options?: Omit<Partial<Toast>, 'type' | 'message'>) => {
    useToastStore.getState().addToast({
      type: 'success',
      message,
      duration: 4000,
      ...options,
    });
  },
  error: (message: string, options?: Omit<Partial<Toast>, 'type' | 'message'>) => {
    useToastStore.getState().addToast({
      type: 'error',
      message,
      duration: 6000,
      ...options,
    });
  },
  warning: (message: string, options?: Omit<Partial<Toast>, 'type' | 'message'>) => {
    useToastStore.getState().addToast({
      type: 'warning',
      message,
      duration: 5000,
      ...options,
    });
  },
  info: (message: string, options?: Omit<Partial<Toast>, 'type' | 'message'>) => {
    useToastStore.getState().addToast({
      type: 'info',
      message,
      duration: 4000,
      ...options,
    });
  },
  loading: (message: string, options?: Omit<Partial<Toast>, 'type' | 'message'>) => {
    const id = generateId();
    useToastStore.getState().addToast({
      id,
      type: 'loading',
      message,
      duration: Infinity,
      dismissible: false,
      ...options,
    });
    return {
      id,
      success: (msg: string, opts?: Omit<Partial<Toast>, 'type' | 'message'>) => {
        useToastStore.getState().updateToast(id, {
          type: 'success',
          message: msg,
          duration: 4000,
          dismissible: true,
          ...opts,
        });
      },
      error: (msg: string, opts?: Omit<Partial<Toast>, 'type' | 'message'>) => {
        useToastStore.getState().updateToast(id, {
          type: 'error',
          message: msg,
          duration: 6000,
          dismissible: true,
          ...opts,
        });
      },
      dismiss: () => useToastStore.getState().removeToast(id),
    };
  },
  custom: (options: Omit<Toast, 'id'>) => {
    useToastStore.getState().addToast(options);
  },
  dismiss: (id: string) => {
    useToastStore.getState().removeToast(id);
  },
  dismissAll: () => {
    useToastStore.getState().clearAll();
  },
};

// Toast icons con colores semánticos
const toastConfig: Record<
  ToastType,
  {
    icon: typeof CheckCircle;
    bg: string;
    border: string;
    text: string;
    iconBg: string;
    iconColor: string;
    progressColor: string;
  }
> = {
  success: {
    icon: CheckCircle,
    bg: 'bg-emerald-50 dark:bg-emerald-950/30',
    border: 'border-emerald-200 dark:border-emerald-800/50',
    text: 'text-emerald-900 dark:text-emerald-100',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/50',
    iconColor: 'text-emerald-600 dark:text-emerald-400',
    progressColor: 'bg-emerald-500',
  },
  error: {
    icon: XCircle,
    bg: 'bg-red-50 dark:bg-red-950/30',
    border: 'border-red-200 dark:border-red-800/50',
    text: 'text-red-900 dark:text-red-100',
    iconBg: 'bg-red-100 dark:bg-red-900/50',
    iconColor: 'text-red-600 dark:text-red-400',
    progressColor: 'bg-red-500',
  },
  warning: {
    icon: Warning,
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-800/50',
    text: 'text-amber-900 dark:text-amber-100',
    iconBg: 'bg-amber-100 dark:bg-amber-900/50',
    iconColor: 'text-amber-600 dark:text-amber-400',
    progressColor: 'bg-amber-500',
  },
  info: {
    icon: Info,
    bg: 'bg-blue-50 dark:bg-blue-950/30',
    border: 'border-blue-200 dark:border-blue-800/50',
    text: 'text-blue-900 dark:text-blue-100',
    iconBg: 'bg-blue-100 dark:bg-blue-900/50',
    iconColor: 'text-blue-600 dark:text-blue-400',
    progressColor: 'bg-blue-500',
  },
  loading: {
    icon: Sparkle,
    bg: 'bg-slate-50 dark:bg-slate-900/50',
    border: 'border-slate-200 dark:border-slate-700/50',
    text: 'text-slate-900 dark:text-slate-100',
    iconBg: 'bg-slate-100 dark:bg-slate-800/50',
    iconColor: 'text-slate-600 dark:text-slate-400',
    progressColor: 'bg-slate-500',
  },
};

interface ToastItemProps {
  toast: Toast;
  onDismiss: () => void;
  index: number;
}

function ToastItem({ toast: toastItem, onDismiss, index }: ToastItemProps) {
  const config = toastConfig[toastItem.type];
  const Icon = config.icon;

  // Auto-dismiss con pausa al hover
  useEffect(() => {
    if (toastItem.duration === Infinity || !toastItem.duration) return;

    let timer: ReturnType<typeof setTimeout>;
    const startTimer = () => {
      timer = setTimeout(() => {
        onDismiss();
      }, toastItem.duration);
    };

    startTimer();
    return () => clearTimeout(timer);
  }, [toastItem.duration, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 100, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.9 }}
      transition={{
        duration: 0.35,
        ease: [0.25, 0.46, 0.45, 0.94],
        delay: index * 0.05,
      }}
      className={cn(
        'relative w-full max-w-[400px] overflow-hidden rounded-2xl border shadow-lg',
        'backdrop-blur-sm',
        config.bg,
        config.border
      )}
      role="alert"
      aria-live="polite"
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
    >
      {/* Progress bar */}
      {toastItem.duration !== Infinity && toastItem.duration && (
        <motion.div
          className={cn('absolute bottom-0 left-0 h-1 rounded-full', config.progressColor)}
          initial={{ width: '100%' }}
          animate={{ width: '0%' }}
          transition={{
            duration: toastItem.duration / 1000,
            ease: 'linear',
          }}
        />
      )}

      <div className="flex items-start gap-3 p-4">
        {/* Icon container */}
        <motion.div
          className={cn('flex-shrink-0 rounded-xl p-2', config.iconBg, config.iconColor)}
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
        >
          {toastItem.type === 'loading' ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            >
              <Icon className="h-5 w-5" weight="fill" />
            </motion.div>
          ) : (
            <Icon className="h-5 w-5" weight="fill" />
          )}
        </motion.div>

        {/* Content */}
        <div className="flex-1 min-w-0 pt-0.5">
          {toastItem.title && (
            <h4 className={cn('text-sm font-semibold leading-tight', config.text)}>
              {toastItem.title}
            </h4>
          )}
          <p
            className={cn(
              'text-sm leading-relaxed',
              toastItem.title ? 'mt-1 text-foreground/80' : config.text
            )}
          >
            {toastItem.message}
          </p>
          {toastItem.description && (
            <p className="mt-1 text-xs text-muted-foreground">{toastItem.description}</p>
          )}

          {/* Action button */}
          {toastItem.action && (
            <motion.button
              onClick={() => {
                toastItem.action?.onClick();
                onDismiss();
              }}
              className={cn(
                'mt-2 text-xs font-medium underline-offset-2 hover:underline',
                config.text
              )}
              whileHover={{ x: 2 }}
              whileTap={{ scale: 0.98 }}
            >
              {toastItem.action.label} →
            </motion.button>
          )}
        </div>

        {/* Dismiss button */}
        {toastItem.dismissible && (
          <motion.button
            onClick={onDismiss}
            className={cn(
              'flex-shrink-0 -mr-1 -mt-1 rounded-lg p-1.5',
              'text-muted-foreground/60 hover:text-foreground hover:bg-black/5',
              'dark:hover:bg-white/10',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1',
              'transition-colors duration-200'
            )}
            aria-label="Cerrar notificación"
            whileHover={{ scale: 1.1, rotate: 90 }}
            whileTap={{ scale: 0.9 }}
          >
            <X className="h-4 w-4" weight="bold" />
          </motion.button>
        )}
      </div>
    </motion.div>
  );
}

export function BeautifulToastContainer() {
  const { toasts, removeToast } = useToastStore();

  return (
    <div
      className="fixed bottom-6 right-6 z-[100] flex flex-col items-end gap-3"
      role="region"
      aria-label="Notificaciones"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toastItem, index) => (
          <ToastItem
            key={toastItem.id}
            toast={toastItem}
            onDismiss={() => removeToast(toastItem.id)}
            index={index}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

// Hook para usar toasts fácilmente
export function useToast() {
  const { addToast, removeToast, clearAll } = useToastStore();

  return {
    toast: {
      success: toast.success,
      error: toast.error,
      warning: toast.warning,
      info: toast.info,
      loading: toast.loading,
      custom: toast.custom,
      dismiss: toast.dismiss,
      dismissAll: toast.dismissAll,
    },
    addToast,
    removeToast,
    clearAll,
  };
}
