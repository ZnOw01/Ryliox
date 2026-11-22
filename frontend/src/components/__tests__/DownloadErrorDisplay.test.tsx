import { render, screen } from '@testing-library/react';

import i18n from '../../i18n/config';
import { ProgressStatus } from '../download-progress/ProgressStatus';
import { downloadErrorMessage } from '../download-progress/utils';

const RAW = 'Session token expired. Please copy fresh cookies from your browser.';

describe('download job errors', () => {
  it('shows a translated message for a known code, raw text only in the details', () => {
    render(
      <ProgressStatus
        currentLabel="error"
        progressPercent={0}
        progress={{ status: 'error', job_id: 'job-1', error: RAW, code: 'session_rejected' }}
      />
    );

    expect(screen.getByText(/o'reilly rechazó la sesión/i)).toBeInTheDocument();
    const raw = screen.getAllByText(new RegExp(RAW.slice(0, 20), 'i'));
    expect(raw).toHaveLength(1);
    expect(raw[0].closest('details')).not.toBeNull();
  });

  it('falls back to the generic translated error when the code is missing or unknown', () => {
    const t = i18n.t;
    const generic = t('download.errors.generic');
    expect(downloadErrorMessage({ status: 'error', error: RAW }, t)).toBe(generic);
    expect(downloadErrorMessage({ status: 'error', error: RAW, code: 'nope' }, t)).toBe(generic);
    expect(generic).not.toMatch(/session/i);
  });

  it('translates in English too', async () => {
    await i18n.changeLanguage('en');
    expect(downloadErrorMessage({ status: 'error', code: 'upstream_blocked' }, i18n.t)).toMatch(
      /temporarily blocking/i
    );
  });
});

describe('running job summary', () => {
  it('does not show the server progress text, which is English', () => {
    render(
      <ProgressStatus
        currentLabel="running"
        progressPercent={82}
        progress={{
          status: 'running',
          job_id: 'job-1',
          percentage: 82,
          message: '82% - Downloading CSS (3/10)',
        }}
      />
    );

    expect(screen.getByText(/estado: en progreso/i)).toBeInTheDocument();
    expect(screen.queryByText(/downloading css/i)).toBeNull();
  });
});
