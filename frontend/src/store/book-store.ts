import { create } from "zustand";

import type { SearchBook } from "../lib/types";

type BookState = {
  selectedBook: SearchBook | null;
  format: string;
  skipImages: boolean;
  setSelectedBook: (book: SearchBook | null) => void;
  setFormat: (format: string) => void;
  setSkipImages: (skipImages: boolean) => void;
  reset: () => void;
};

const DEFAULT_FORMAT = "epub";

export const useBookStore = create<BookState>((set) => ({
  selectedBook: null,
  format: DEFAULT_FORMAT,
  skipImages: false,
  setSelectedBook: (selectedBook) => set({ selectedBook }),
  setFormat: (format) => set({ format }),
  setSkipImages: (skipImages) => set({ skipImages }),
  reset: () =>
    set({
      selectedBook: null,
      format: DEFAULT_FORMAT,
      skipImages: false
    })
}));
