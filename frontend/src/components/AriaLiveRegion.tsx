import { create } from 'zustand';

interface AnnouncementState {
  message: string;
  priority: 'polite' | 'assertive';
  announce: (message: string, priority?: 'polite' | 'assertive') => void;
  clear: () => void;
}

export const useAnnouncementStore = create<AnnouncementState>(set => ({
  message: '',
  priority: 'polite',
  announce: (message, priority = 'polite') => set({ message, priority }),
  clear: () => set({ message: '' }),
}));

// Helper to announce to screen readers
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite') {
  useAnnouncementStore.getState().announce(message, priority);
}

// ARIA Live Region component
export function AriaLiveRegion() {
  const { message, priority } = useAnnouncementStore();

  return (
    <div className="sr-only" aria-live={priority} aria-atomic="true">
      {message}
    </div>
  );
}
