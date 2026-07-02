import { fireEvent, render, screen } from '@testing-library/react';

import { SearchBooksCard } from '../SearchBooksCard';
import { useBookStore } from '../../store/book-store';

vi.mock('../../lib/use-debounced-value', () => ({
  useDebouncedValue: <T,>(value: T) => value,
}));

vi.mock('@tanstack/react-query', async () => {
  const actual =
    await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQueryClient: vi.fn(() => ({
      invalidateQueries: vi.fn(),
      removeQueries: vi.fn(),
      setQueryData: vi.fn(),
    })),
    useQuery: vi.fn((options: { enabled?: boolean }) => ({
      data: options.enabled
        ? {
            results: [
              {
                id: '9781',
                title: 'Python limpio',
                authors: ['Autor Demo'],
                publishers: ["O'Reilly"],
              },
            ],
          }
        : undefined,
      error: null,
      isPending: false,
      isFetching: false,
    })),
  };
});

describe('SearchBooksCard', () => {
  beforeEach(() => {
    useBookStore.getState().reset();
    window.history.replaceState(null, '', '/');
  });

  it('renders an accessible search box and listbox options', async () => {
    render(<SearchBooksCard />);

    const input = screen.getByRole('textbox', { name: /buscar libros/i });
    fireEvent.change(input, { target: { value: 'python' } });

    expect(input).toHaveAttribute('aria-controls', 'search-results');
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /python limpio/i })).toBeInTheDocument();
  });

  it('marks the selected option with aria-selected', () => {
    render(<SearchBooksCard />);

    const input = screen.getByRole('textbox', { name: /buscar libros/i });
    fireEvent.change(input, { target: { value: 'python' } });

    const option = screen.getByRole('option', { name: /python limpio/i });
    fireEvent.click(option);

    expect(option).toHaveAttribute('aria-selected', 'true');
  });
});
