// BMS title sort convention (bms_title_sort.md):
//   0: ASCII punctuation & digits  (!"#$%...0-9)
//   1: ASCII letters               (A-Z a-z)
//   2: non-ASCII symbols           (★ ☆ etc.)
//   3: Hiragana                    (U+3040–U+309F)
//   4: Katakana                    (U+30A0–U+30FF)
//   5: CJK / Kanji                 (U+4E00–U+9FFF + Ext-A)
export function charSortGroup(ch: string): number {
  const code = ch.codePointAt(0) ?? 0;
  if (code >= 0x21 && code <= 0x7e) {
    if ((code >= 0x41 && code <= 0x5a) || (code >= 0x61 && code <= 0x7a)) return 1;
    return 0;
  }
  if (code >= 0x3040 && code <= 0x309f) return 3;
  if (code >= 0x30a0 && code <= 0x30ff) return 4;
  if ((code >= 0x4e00 && code <= 0x9fff) || (code >= 0x3400 && code <= 0x4dbf)) return 5;
  return 2;
}

export function compareTitles(a: string, b: string): number {
  const ga = charSortGroup([...a][0] ?? "");
  const gb = charSortGroup([...b][0] ?? "");
  if (ga !== gb) return ga - gb;
  return a.localeCompare(b);
}
