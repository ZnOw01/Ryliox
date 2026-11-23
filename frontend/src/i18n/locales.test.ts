import en from './locales/en.json';
import es from './locales/es.json';

type Tree = { [key: string]: string | string[] | Tree };

function flatten(tree: Tree, prefix = ''): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    if (typeof value === 'string' || Array.isArray(value)) {
      out.set(prefix + key, JSON.stringify(value));
    } else {
      for (const [k, v] of flatten(value, `${prefix}${key}.`)) out.set(k, v);
    }
  }
  return out;
}

// Words that are spelled the same in both languages.
const SAME_IN_BOTH = new Set([
  'app.title',
  'common.error',
  'common.no',
  'download.progress.error',
  'download.progress.status_error',
  'download.progress.percentage',
  'download.progress.percentage_aria',
  'keyboard_shortcuts.general',
]);

describe('locale files', () => {
  const esKeys = flatten(es as Tree);
  const enKeys = flatten(en as Tree);

  it('define the same keys', () => {
    expect([...esKeys.keys()].sort()).toEqual([...enKeys.keys()].sort());
  });

  it('translate every Spanish string', () => {
    const untranslated = [...esKeys].filter(
      ([key, value]) => !SAME_IN_BOTH.has(key) && enKeys.get(key) === value
    );
    expect(untranslated).toEqual([]);
  });
});
