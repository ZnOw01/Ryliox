import '@testing-library/jest-dom/vitest';

import i18n from './src/i18n/config';

const localStorageData = new Map<string, string>();

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: {
    clear: () => localStorageData.clear(),
    getItem: (key: string) => localStorageData.get(key) ?? null,
    key: (index: number) => Array.from(localStorageData.keys())[index] ?? null,
    removeItem: (key: string) => localStorageData.delete(key),
    setItem: (key: string, value: string) => localStorageData.set(key, String(value)),
    get length() {
      return localStorageData.size;
    },
  },
});

await i18n.changeLanguage('es');

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  configurable: true,
  value() {
    return undefined;
  },
});
