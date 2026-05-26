import assert from "node:assert/strict";
import test from "node:test";
import i18next from "i18next";

import { getProfileSaveErrorMessage } from "./profile-errors.mjs";
import { resources } from "./i18n/resources.mjs";

async function translator(language) {
  const instance = i18next.createInstance();
  await instance.init({
    resources,
    lng: language,
    fallbackLng: "ko",
    interpolation: { escapeValue: false },
  });
  return instance.t.bind(instance);
}

test("profile username duplicate error is localized", async () => {
  assert.equal(
    getProfileSaveErrorMessage(new Error("USERNAME_ALREADY_EXISTS"), await translator("ko")),
    "동일한 유저명이 이미 존재합니다",
  );
  assert.equal(
    getProfileSaveErrorMessage(new Error("USERNAME_ALREADY_EXISTS"), await translator("en")),
    "This username is already taken.",
  );
  assert.equal(
    getProfileSaveErrorMessage(new Error("USERNAME_ALREADY_EXISTS"), await translator("ja")),
    "同じユーザー名がすでに存在します。",
  );
});

test("unknown profile save errors keep their server message", async () => {
  assert.equal(
    getProfileSaveErrorMessage(new Error("Something failed"), await translator("en")),
    "Something failed",
  );
});
