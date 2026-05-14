import test from "node:test";
import assert from "node:assert/strict";
import i18next from "i18next";
import { resources } from "./resources.mjs";

test("web translations interpolate user and music data without translating it", async () => {
  const instance = i18next.createInstance();
  await instance.init({
    resources,
    lng: "ja",
    fallbackLng: "ko",
    interpolation: { escapeValue: false },
  });

  const rendered = instance.t("profile.header.lastSyncedByUser", {
    username: "RED_BMS_Player",
    tableName: "Satellite",
    title: "★LittlE HearTs★",
    artist: "ねこみりん",
  });

  assert.match(rendered, /RED_BMS_Player/);
  assert.match(rendered, /Satellite/);
  assert.match(rendered, /★LittlE HearTs★/);
  assert.match(rendered, /ねこみりん/);
});
