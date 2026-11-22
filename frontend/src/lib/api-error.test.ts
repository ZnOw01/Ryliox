import { afterEach, describe, expect, it } from 'vitest';

import i18n from '../i18n/config';
import { formatDescription } from '../components/download-progress/utils';
import { ApiError } from './api';
import { parseApiError } from './api-error';

afterEach(async () => {
  await i18n.changeLanguage('es');
});

describe('server text shown in the UI language', () => {
  const rejectedCookies = new ApiError(
    {
      error: 'Cookies saved but session is still invalid.',
      code: 'invalid_session_after_cookies',
    },
    401
  );

  it.each(['es', 'en'])('explains rejected cookies in %s', async language => {
    await i18n.changeLanguage(language);

    const { message } = parseApiError(rejectedCookies);

    expect(message).toBe(i18n.t('errors.invalid_session_after_cookies'));
    expect(message).not.toContain('still invalid');
  });

  it('describes known formats itself and falls back to the server for new ones', async () => {
    await i18n.changeLanguage('es');
    const t = i18n.t;

    expect(formatDescription('pdf', t, 'Single PDF with the whole book')).toBe(
      'Un solo PDF con el libro entero o los capítulos elegidos'
    );
    expect(formatDescription('mobi', t, 'Kindle format')).toBe('Kindle format');
    expect(formatDescription('mobi', t)).toBeUndefined();
  });
});
