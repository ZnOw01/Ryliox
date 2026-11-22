import i18n from './config';

describe('plural keys', () => {
  it.each([
    ['es', 1, '1 resultado'],
    ['es', 10, '10 resultados'],
    ['en', 1, '1 result'],
    ['en', 10, '10 results'],
  ])('search.results_count in %s for %i', async (language, count, expected) => {
    await i18n.changeLanguage(language);
    expect(i18n.t('search.results_count', { count })).toBe(expected);
  });

  it.each([
    ['es', 1, '1 seleccionado'],
    ['es', 3, '3 seleccionados'],
  ])('download.chapters.selected_count in %s for %i', async (language, count, expected) => {
    await i18n.changeLanguage(language);
    expect(i18n.t('download.chapters.selected_count', { count })).toBe(expected);
  });
});
