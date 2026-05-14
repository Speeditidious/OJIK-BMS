import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../..", import.meta.url).pathname;
const allowed = [
  "web/src/lib/i18n/resources.mjs",
  "web/src/lib/i18n/resources.ts",
  "web/src/components/theme-toggle.tsx",
  // Korean contributor/tester usernames — proper nouns, not translatable UI strings
  "web/src/app/contributors/page.tsx",
];

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) return walk(path);
    return /\.(ts|tsx)$/.test(path) ? [path] : [];
  });
}

const offenders = walk(root).filter((path) => {
  const normalized = path.replace(/\\/g, "/");
  if (allowed.some((item) => normalized.endsWith(item.replace(/\\/g, "/")))) return false;
  const text = readFileSync(path, "utf8");
  return /\p{Script=Hangul}/u.test(text);
});

if (offenders.length > 0) {
  console.error(offenders.join("\n"));
  process.exit(1);
}
