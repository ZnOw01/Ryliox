import { render, screen } from "@testing-library/react";

import { ChapterSelector } from "../ChapterSelector";

describe("ChapterSelector", () => {
  it("renders chapter metadata when available", () => {
    render(
      <ChapterSelector
        chapters={[
          {
            index: 0,
            title: "Introduccion",
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
        selectedBook={{ id: "demo", title: "Demo" }}
        selectedChapterIndexes={[]}
        selectedChapterSet={new Set()}
        selectable={false}
        totalChapters={1}
      />,
    );

    expect(screen.getByText("12 paginas | 7.5 min lectura")).toBeInTheDocument();
  });
});
