import assert from "node:assert/strict";

import { resolveCourseClearDisplay } from "./course-update-clear-core.mjs";

assert.deepEqual(
  resolveCourseClearDisplay({
    clear: null,
    previousState: { clear_type: 5 },
    currentState: { clear_type: 5 },
  }),
  { previous: 5, current: 5, changed: false },
);

assert.deepEqual(
  resolveCourseClearDisplay({
    clear: { prev: 4, new: 5 },
    previousState: { clear_type: 4 },
    currentState: { clear_type: 5 },
  }),
  { previous: 4, current: 5, changed: true },
);
