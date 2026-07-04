import { render, screen } from '@testing-library/react';

import { ChapterSelector } from '../ChapterSelector';

describe('ChapterSelector', () => {
  it('renders chapter metadata when available', () => {
    render(
      <ChapterSelector
        chapters={[
          {
            index: 0,
            title: 'Introduccion',
            pages: 12,
            minutes: 7.5,
          },
        ]}
        error={null}
        hasData
        isFetching={false}
        isLoading={false}
        onClear={() => {}}
        onSelectAll={() => {}}
        onToggleChapter={() => {}}
        selectedBook={{ id: 'demo', title: 'Demo' }}
        selectedChapterIndexes={[]}
        selectedChapterSet={new Set()}
        selectable={false}
        totalChapters={1}
      />
    );

    expect(screen.getByText('Introduccion')).toBeInTheDocument();
    expect(screen.getByText('1 en total')).toBeInTheDocument();
  });

  it('renders advanced tools when selectable for PDF', () => {
    render(
      <ChapterSelector
        chapters={[
          { index: 0, title: 'Chapter 1' },
          { index: 1, title: 'Chapter 2' },
        ]}
        error={null}
        hasData
        isFetching={false}
        isLoading={false}
        onClear={() => {}}
        onSelectAll={() => {}}
        onToggleChapter={() => {}}
        selectedBook={{ id: 'demo', title: 'Demo' }}
        selectedChapterIndexes={[]}
        selectedChapterSet={new Set()}
        selectable={true}
        totalChapters={2}
      />
    );

    expect(screen.getByPlaceholderText('Buscar capítulo...')).toBeInTheDocument();
    expect(screen.getByText('Presets:')).toBeInTheDocument();
  });

  it('collapses chapters list when non-selectable for EPUB', () => {
    render(
      <ChapterSelector
        chapters={[
          { index: 0, title: 'Chapter 1' },
          { index: 1, title: 'Chapter 2' },
          { index: 2, title: 'Chapter 3' },
          { index: 3, title: 'Chapter 4' },
        ]}
        error={null}
        hasData
        isFetching={false}
        isLoading={false}
        onClear={() => {}}
        onSelectAll={() => {}}
        onToggleChapter={() => {}}
        selectedBook={{ id: 'demo', title: 'Demo' }}
        selectedChapterIndexes={[]}
        selectedChapterSet={new Set()}
        selectable={false}
        totalChapters={4}
      />
    );

    expect(screen.getByText('Chapter 1')).toBeInTheDocument();
    expect(screen.getByText('Chapter 2')).toBeInTheDocument();
    expect(screen.getByText('Chapter 3')).toBeInTheDocument();
    expect(screen.queryByText('Chapter 4')).not.toBeInTheDocument();
    expect(screen.getByText('Ver todos los capítulos (4)')).toBeInTheDocument();
  });
});
