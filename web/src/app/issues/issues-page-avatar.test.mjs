import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "[issueId]", "page.tsx"), "utf8");

assert.match(
  source,
  /import\s+\{\s*AvatarImage\s*\}\s+from\s+["']@\/components\/common\/AvatarImage["']/,
  "Issue avatars must use AvatarImage so broken URLs fall back to initials.",
);

assert.match(
  source,
  /src=\{resolveAvatarUrl\(avatarUrl\)\}/,
  "Issue avatar URLs must be normalized so /uploads avatars load from the API origin.",
);

assert.equal(
  /<img\s+src=\{avatarUrl\}/.test(source),
  false,
  "Issue avatars must not render raw avatarUrl values directly.",
);
