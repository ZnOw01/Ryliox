import { describe, expect, it } from 'vitest';

import { mergeProgressUpdate } from './useDownloadManager';

describe('mergeProgressUpdate', () => {
  it('rejects updates for a different active job', () => {
    const current = { job_id: 'job-2', status: 'running', percentage: 40 };

    expect(
      mergeProgressUpdate(
        current,
        { job_id: 'job-1', status: 'completed', percentage: 100 },
        'job-2'
      )
    ).toBe(current);
  });

  it('does not regress status or percentage for the same job', () => {
    const current = { job_id: 'job-1', status: 'running', percentage: 60 };

    expect(
      mergeProgressUpdate(current, { job_id: 'job-1', status: 'queued', percentage: 0 }, 'job-1')
    ).toBe(current);
    expect(
      mergeProgressUpdate(current, { job_id: 'job-1', status: 'running', percentage: 40 }, 'job-1')
    ).toBe(current);
  });

  it('keeps terminal states immutable and accepts forward progress', () => {
    const running = { job_id: 'job-1', status: 'running', percentage: 60 };
    const completed = { job_id: 'job-1', status: 'completed', percentage: 100 };

    expect(mergeProgressUpdate(running, completed, 'job-1')).toBe(completed);
    expect(
      mergeProgressUpdate(
        completed,
        { job_id: 'job-1', status: 'running', percentage: 80 },
        'job-1'
      )
    ).toBe(completed);
  });
});
