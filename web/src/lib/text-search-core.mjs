export function normalizeLooseSearchText(value) {
  return String(value ?? "")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

export function textMatchesLooseQuery(value, query) {
  const normalizedQuery = normalizeLooseSearchText(query);
  if (!normalizedQuery) return true;
  return normalizeLooseSearchText(value).includes(normalizedQuery);
}

export function anyTextMatchesLooseQuery(values, query) {
  return values.some((value) => textMatchesLooseQuery(value, query));
}
