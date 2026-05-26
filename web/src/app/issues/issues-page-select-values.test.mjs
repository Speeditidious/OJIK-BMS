import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "page.tsx"), "utf8");

assert.equal(
  /<SelectItem\s+value=["']["']/.test(source),
  false,
  "Radix SelectItem values must not be empty strings",
);
