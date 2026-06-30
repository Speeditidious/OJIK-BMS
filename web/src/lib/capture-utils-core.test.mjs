import assert from "node:assert/strict";
import test from "node:test";

import { getCaptureErrorMessage } from "./capture-utils-core.mjs";

test("capture Event errors are converted to a readable message", () => {
  const eventLike = { type: "error", target: { currentSrc: "https://cdn.example/avatar.png" } };

  assert.equal(
    getCaptureErrorMessage(eventLike),
    "Image failed to load while generating the preview: https://cdn.example/avatar.png",
  );
});

test("capture Error objects keep their message", () => {
  assert.equal(
    getCaptureErrorMessage(new Error("canvas is too large")),
    "canvas is too large",
  );
});
