import i18n from '../../../i18n/config';
import { formatStatusLabel } from '../utils';

describe('formatStatusLabel', () => {
  it('labels every status the UI can be in, including the optimistic cancelling', () => {
    const t = i18n.t;
    for (const status of ['idle', 'queued', 'running', 'cancelling', 'completed', 'error']) {
      expect(formatStatusLabel(status, t)).not.toBe(status);
    }
    expect(formatStatusLabel('cancelling', t)).toBe('Cancelando');
  });
});
