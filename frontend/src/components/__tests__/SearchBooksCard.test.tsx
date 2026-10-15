import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';

import { queryKeys } from '../../lib/query-keys';
import { useBookStore } from '../../store/book-store';
import { SearchBooksCard } from '../SearchBooksCard';

function renderSearchCard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity, retry: false } },
  });
  queryClient.setQueryData(queryKeys.search.byQuery('python'), {
    results: [
      {
        id: '9781',
        title: 'Python limpio',
        authors: ['Autor Demo'],
        publishers: ["O'Reilly"],
      },
    ],
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SearchBooksCard />
    </QueryClientProvider>
  );
}

describe('SearchBooksCard', () => {
  beforeEach(() => {
    useBookStore.getState().reset();
    window.history.replaceState(null, '', '/');
  });

  it('renders an accessible search box and listbox options', async () => {
    renderSearchCard();

    const input = screen.getByRole('combobox', { name: /buscar libros/i });
    fireEvent.change(input, { target: { value: 'python' } });

    const listbox = screen.getByRole('listbox');
    expect(input).toHaveAttribute('aria-controls', listbox.id);
    expect(screen.getByRole('option', { name: /python limpio/i })).toBeInTheDocument();
  });

  it('marks the selected option with aria-selected', () => {
    renderSearchCard();

    const input = screen.getByRole('combobox', { name: /buscar libros/i });
    fireEvent.change(input, { target: { value: 'python' } });

    const option = screen.getByRole('option', { name: /python limpio/i });
    fireEvent.click(option);

    expect(option).toHaveAttribute('aria-selected', 'true');
  });
});
