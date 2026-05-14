import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./client.tsx", import.meta.url), "utf8");
const match = source.match(
  /function ensureI18nInitialized\(language: LanguageCode\) \{([\s\S]*?)\n\}/,
);

assert.ok(match, "ensureI18nInitialized should exist");
assert.equal(
  match[1].includes("changeLanguage"),
  false,
  "ensureI18nInitialized must not call changeLanguage during render",
);
