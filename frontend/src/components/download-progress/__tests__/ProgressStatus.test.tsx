import { act, fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import { ApiError, revealFile } from '../../../lib/api';
import { ProgressStatus } from '../ProgressStatus';

vi.mock('../../../lib/api', async importOriginal => ({
  ...(await importOriginal<typeof import('../../../lib/api')>()),
  revealFile: vi.fn(),
}));

describe('ProgressStatus', () => {
  it('shows a cancelled summary state', () => {
    render(
      <ProgressStatus
        currentLabel="cancelled"
        progressPercent={0}
        progress={{
          status: 'cancelled',
          job_id: 'job-1',
          error: 'Download cancelled by user',
          code: 'download_cancelled',
        }}
      />
    );

    expect(screen.getByText(/estado: cancelado/i)).toBeInTheDocument();
    expect(screen.getByText(/download cancelled by user/i)).toBeInTheDocument();
  });

  it('shows a canceled summary state (US spelling)', () => {
    render(
      <ProgressStatus
        currentLabel="canceled"
        progressPercent={0}
        progress={{
          status: 'canceled',
          job_id: 'job-2',
        }}
      />
    );

    expect(screen.getByText(/estado: cancelado/i)).toBeInTheDocument();
  });

  it('explains a failed reveal in the UI language', async () => {
    vi.mocked(revealFile).mockRejectedValueOnce(
      new ApiError({ error: 'Path does not exist', code: 'path_not_found' }, 404)
    );
    render(
      <ProgressStatus
        currentLabel="completed"
        progressPercent={100}
        progress={{ status: 'completed', job_id: 'job-4', epub: '/out/book.epub' }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /abrir ubicación/i }));

    expect(await screen.findByText('El archivo ya no existe.')).toBeInTheDocument();
    expect(screen.queryByText('Path does not exist')).toBeNull();
  });

  it('clears the copied-path timer on unmount', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    vi.useFakeTimers();
    try {
      const view = render(
        <ProgressStatus
          currentLabel="completed"
          progressPercent={100}
          progress={{ status: 'completed', job_id: 'job-3', epub: '/out/book.epub' }}
        />
      );
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copiar ruta/i }));
      });
      expect(screen.getAllByText(/ruta copiada/i).length).toBeGreaterThan(0);

      view.unmount();

      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
