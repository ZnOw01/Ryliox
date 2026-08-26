import { create } from 'zustand';

interface AnnouncementState {
  message: string;
  priority: 'polite' | 'assertive';
  counter: number;
  announce: (message: string, priority?: 'polite' | 'assertive') => void;
  clear: () => void;
}

export const useAnnouncementStore = create<AnnouncementState>(set => ({
  message: '',
  priority: 'polite',
  counter: 0,
  announce: (message, priority = 'polite') =>
    set(state => ({ message, priority, counter: state.counter + 1 })),
  clear: () => set({ message: '', counter: 0 }),
}));

// Helper to announce to screen readers
export function announce(message: string, priority: 'polite' | 'assertive' = 'polite') {
  useAnnouncementStore.getState().announce(message, priority);
}

// ARIA Live Region component
export function AriaLiveRegion() {
  const { message, priority, counter } = useAnnouncementStore();

  return (
    <div className="sr-only" aria-live={priority} aria-atomic="true">
      {message ? `${message}${counter % 2 === 0 ? '\u200B' : ''}` : ''}
    </div>
  );
}
