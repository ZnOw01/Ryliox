import { afterEach, describe, expect, it, vi } from 'vitest';

import { getHealth, startDownload } from './api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('API retry policy', () => {
  it('does not retry a failed download POST', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{"error":"failed"}', { status: 503 }));

    await expect(
      startDownload({
        book_id: 'book',
        format: 'epub',
        skip_images: false,
      })
    ).rejects.toMatchObject({ status: 503 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('retries a transient GET', async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{"error":"failed"}', { status: 503 }))
      .mockResolvedValueOnce(new Response('{"status":"ok"}', { status: 200 }));

    const request = getHealth();
    await vi.runAllTimersAsync();

    await expect(request).resolves.toEqual({ status: 'ok' });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
