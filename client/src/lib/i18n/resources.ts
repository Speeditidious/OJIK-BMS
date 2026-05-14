// resources.mjs is shared with Node-based i18n tests.
// @ts-expect-error TypeScript does not attach declarations to this local .mjs wrapper in the Vite client config.
export { resources } from "./resources.mjs";
