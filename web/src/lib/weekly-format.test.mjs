import assert from "node:assert/strict";
import test from "node:test";
import { formatRollover } from "./weekly-format.mjs";

const BASE = { timezone: "Asia/Seoul", day_of_week: "mon", hour: 4, minute: 0 };

test("ko: AM rollover with no minute", () => {
  assert.equal(formatRollover(BASE, "ko"), "매주 월요일 오전 4시 KST 갱신");
});

test("en: AM rollover", () => {
  assert.equal(formatRollover(BASE, "en"), "Updates every Monday at 4:00 AM KST");
});

test("ja: AM rollover with no minute", () => {
  assert.equal(formatRollover(BASE, "ja"), "毎週月曜日 午前4時 KST 更新");
});

test("ko: PM hour with non-zero minute", () => {
  assert.equal(formatRollover({ ...BASE, hour: 14, minute: 30 }, "ko"), "매주 월요일 오후 2시 30분 KST 갱신");
});

test("en: PM hour", () => {
  assert.equal(formatRollover({ ...BASE, hour: 13 }, "en"), "Updates every Monday at 1:00 PM KST");
});

test("non-Seoul timezone passed through as-is", () => {
  assert.equal(formatRollover({ ...BASE, timezone: "UTC" }, "ko"), "매주 월요일 오전 4시 UTC 갱신");
});

test("unknown language falls back to en", () => {
  const result = formatRollover(BASE, "zh");
  assert.ok(result.includes("Monday"), `Expected English fallback, got: ${result}`);
});
