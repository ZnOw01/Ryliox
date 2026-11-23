import { render, screen } from '@testing-library/react';

import { ApiError } from '../../../lib/api';
import { ErrorNotice } from '../ErrorNotice';

describe('ErrorNotice', () => {
  it('uses theme tokens so it follows dark mode', () => {
    const { container } = render(
      <ErrorNotice
        error={new ApiError({ error: 'x', code: 'internal_error', details: { a: 1 } }, 500)}
      />
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    const fixedLight = Array.from(container.querySelectorAll<HTMLElement>('*')).filter(el =>
      /\b(bg-white|bg-red-50|text-red-\d+)\b/.test(el.getAttribute('class') ?? '')
    );
    expect(fixedLight).toEqual([]);
  });
});
