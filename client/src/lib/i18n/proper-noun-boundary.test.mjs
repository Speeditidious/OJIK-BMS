import test from "node:test";
import assert from "node:assert/strict";
import i18next from "i18next";
import { resources } from "./resources.mjs";

test("client translations interpolate paths and file names without translating them", async () => {
  const instance = i18next.createInstance();
  await instance.init({
    resources,
    lng: "en",
    fallbackLng: "ko",
    interpolation: { escapeValue: false },
  });

  const rendered = instance.t("client.source.validation.fileNameRequired", {
    fileName: "songdata.db",
    path: "C:/Games/beatoraja/songdata.db",
    clientName: "beatoraja",
  });

  assert.match(rendered, /songdata\.db/);
  assert.match(rendered, /C:\/Games\/beatoraja\/songdata\.db/);
  assert.match(rendered, /beatoraja/);
});
