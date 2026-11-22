import { render } from '@testing-library/react';
import { vi } from 'vitest';

import type { ProgressResponse } from '../../lib/types';
import { DownloadProgressCard } from '../DownloadProgressCard';
import { toast } from '../ui/BeautifulToast';

let progress: ProgressResponse | undefined;
let activeJobId: string | null = null;

vi.mock('../../hooks/useDownloadManager', () => ({
  TERMINAL_DOWNLOAD_STATES: new Set(['completed', 'error', 'cancelled', 'canceled']),
  useDownloadManager: () => ({
    active: false,
    activeJobId,
    bookOnlyFormats: new Set<string>(),
    cancelMutation: { error: null, isPending: false, mutate: () => {} },
    chaptersLoading: false,
    chaptersQuery: { data: undefined, error: null },
    chaptersRefreshing: false,
    clearSelectedChapters: () => {},
    currentLabel: progress?.status ?? 'idle',
    forceReconnect: () => {},
    format: 'epub',
    formats: ['epub'],
    formatsDisabled: false,
    formatsQuery: { data: undefined, error: null, isLoading: false },
    hasChapterSelection: false,
    invalidFormatWithChapterSelection: false,
    progressPercent: 0,
    progressQuery: { data: progress, error: null },
    selectedChapterIndexes: [],
    selectedChapterSet: new Set<number>(),
    selectedBook: null,
    selectAllChapters: () => {},
    setFormat: () => {},
    setSkipImages: () => {},
    skipImages: false,
    sseStatus: 'disconnected',
    startDisabledReason: null,
    startMutation: { error: null, isPending: false, mutate: () => {} },
    toggleChapter: () => {},
    totalChapters: 0,
  }),
}));

describe('DownloadProgressCard notifications', () => {
  beforeEach(() => {
    vi.spyOn(toast, 'success').mockImplementation(() => '');
    vi.spyOn(toast, 'error').mockImplementation(() => '');
  });

  afterEach(() => {
    activeJobId = null;
    vi.restoreAllMocks();
  });

  it('does not announce a job that had already finished when the page loaded', () => {
    progress = { job_id: 'old', status: 'completed', percentage: 100 };

    render(<DownloadProgressCard />);

    expect(toast.success).not.toHaveBeenCalled();
  });

  it('announces a job that finishes while the page is open', () => {
    progress = { job_id: 'job-1', status: 'running', percentage: 40 };
    const view = render(<DownloadProgressCard />);

    progress = { job_id: 'job-1', status: 'error', error: 'boom', code: 'download_failed' };
    view.rerender(<DownloadProgressCard />);

    expect(toast.error).toHaveBeenCalledTimes(1);
  });

  it('announces a job this page started even if it fails before any progress', () => {
    activeJobId = 'job-2';
    progress = { job_id: 'job-2', status: 'error', error: 'boom', code: 'session_rejected' };

    render(<DownloadProgressCard />);

    expect(toast.error).toHaveBeenCalledTimes(1);
  });
});
