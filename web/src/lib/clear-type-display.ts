export function displayClearType(
  clearType: number | null,
  {
    exscore,
    rate,
  }: {
    exscore?: number | null;
    rate?: number | null;
  } = {},
): number | null {
  if (clearType !== 9) return clearType;
  if (exscore === 0) return 7;
  if (rate != null && rate !== 100) return 8;
  return clearType;
}
