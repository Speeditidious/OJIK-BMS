import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resources } from "../lib/i18n/resources.mjs";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

test("public info copy removes beta wording from footer and disclaimer", () => {
  for (const [language, bundle] of Object.entries(resources)) {
    const { legal, footer } = bundle.translation;
    const disclaimer = legal.sections.find((section) => section.title === "면책 조항" || section.title === "Disclaimer" || section.title === "免責事項");

    assert.ok(disclaimer, `${language} disclaimer exists`);
    assert.doesNotMatch(footer.tagline, /beta|베타/i, `${language} footer tagline`);
    assert.equal(footer.beta, "", `${language} footer beta label is empty`);
    assert.doesNotMatch(disclaimer.body, /beta|베타/i, `${language} disclaimer body`);
  }
});

test("support page copy points users to the issue page", () => {
  const koSupport = resources.ko.translation.support.sections;

  assert.deepEqual(
    koSupport.map((section) => section.title),
    ["후원 관련 안내", "버그 제보 및 제안"],
  );
  assert.equal(koSupport[0].body, "지금은 별도의 후원 수단을 열어두지 않았습니다.");
  assert.equal(koSupport[1].link.href, "/issues");
  assert.equal(koSupport[1].link.label, "이슈 페이지");

  const supportPageSource = readFileSync(new URL("./support/page.tsx", import.meta.url), "utf8");

  assert.match(supportPageSource, /href=\{section\.link\.href\}/);
});
