import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';
import i18n from '../../i18n/config';
import { AuthStatusCard } from '../AuthStatusCard';

vi.mock('../../lib/api', () => ({
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
