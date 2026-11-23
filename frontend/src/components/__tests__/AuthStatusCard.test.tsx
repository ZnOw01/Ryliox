import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';
import i18n from '../../i18n/config';
import { getStatus } from '../../lib/api';
import { AuthStatusCard } from '../AuthStatusCard';

vi.mock('../../lib/api', async importOriginal => ({
  ...(await importOriginal<typeof import('../../lib/api')>()),
  getStatus: vi.fn().mockResolvedValue({
    valid: false,
    has_cookies: false,
    reason: 'not_authenticated',
  }),
  getHealth: vi.fn().mockResolvedValue({ status: 'degraded', uptime_seconds: 1 }),
  getCookies: vi.fn().mockResolvedValue({ cookies: {} }),
  saveCookies: vi.fn(),
}));

describe('AuthStatusCard i18n', () => {
  it('renders dynamic service and clipboard labels in English', async () => {
    const originalLanguage = i18n.language;
    await i18n.changeLanguage('en');
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <AuthStatusCard />
      </QueryClientProvider>
    );

    try {
      expect(await screen.findByText('Service: degraded')).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText('Cookies (JSON or HTTP header)'), {
        target: { value: '{"session":"value"}' },
      });
      expect(screen.getByTitle('Copy to clipboard')).toBeInTheDocument();
      expect(screen.getByLabelText('Copy JSON to clipboard')).toBeInTheDocument();
      expect(screen.queryByText('Servicio: degraded')).not.toBeInTheDocument();
    } finally {
      view.unmount();
      queryClient.clear();
      await i18n.changeLanguage(originalLanguage);
    }
  });
});

describe('AuthStatusCard copy button', () => {
  it('clears the copied-cookies timer on unmount', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <AuthStatusCard />
      </QueryClientProvider>
    );
    fireEvent.change(await screen.findByLabelText('Cookies (JSON o encabezado HTTP)'), {
      target: { value: '{"session":"value"}' },
    });
    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(screen.getByLabelText('Copiar JSON al portapapeles'));
      });
      expect(screen.getByText('Copiado')).toBeInTheDocument();

      view.unmount();
      queryClient.clear();

      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('AuthStatusCard with a valid session', () => {
  it('describes stored cookies in the UI language', async () => {
    vi.mocked(getStatus).mockResolvedValueOnce({ valid: true, has_cookies: true, reason: null });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <AuthStatusCard />
      </QueryClientProvider>
    );

    try {
      expect(await screen.findByText('Cookies cifradas en el servidor')).toBeInTheDocument();
      expect(screen.queryByText(/sqlite vault/i)).toBeNull();
    } finally {
      view.unmount();
      queryClient.clear();
    }
  });
});
