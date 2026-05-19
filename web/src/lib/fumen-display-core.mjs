const HTML_ENTITY_MAP = new Map([
  ["amp", "&"],
  ["apos", "'"],
  ["gt", ">"],
  ["lt", "<"],
  ["quot", '"'],
]);

function isValidCodePoint(value) {
  return Number.isInteger(value) && value >= 0 && value <= 0x10FFFF;
}

function decodeEntity(entity) {
  if (entity.startsWith("#x") || entity.startsWith("#X")) {
    const codePoint = Number.parseInt(entity.slice(2), 16);
    return isValidCodePoint(codePoint) ? String.fromCodePoint(codePoint) : `&${entity};`;
  }
  if (entity.startsWith("#")) {
    const codePoint = Number.parseInt(entity.slice(1), 10);
    return isValidCodePoint(codePoint) ? String.fromCodePoint(codePoint) : `&${entity};`;
  }
  return HTML_ENTITY_MAP.get(entity) ?? `&${entity};`;
}

export function decodeFumenDisplayText(value) {
  if (typeof value !== "string" || !value.includes("&")) return value;

  let decoded = value;
  for (let i = 0; i < 3; i += 1) {
    const next = decoded.replace(/&(#\d+|#x[0-9a-fA-F]+|#X[0-9a-fA-F]+|amp|apos|gt|lt|quot);/g, (_, entity) => (
      decodeEntity(entity)
    ));
    if (next === decoded) break;
    decoded = next;
  }
  return decoded;
}
