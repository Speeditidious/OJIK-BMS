interface InitialBrowserUrl {
  pathname: string;
  search: string;
  hash: string;
}

declare global {
  interface Window {
    __OJIK_INITIAL_URL__?: InitialBrowserUrl;
  }
}

export function getInitialBrowserPathname(): string {
  if (typeof window === "undefined") return "";
  return window.__OJIK_INITIAL_URL__?.pathname ?? window.location.pathname;
}

export function getInitialBrowserSearch(): string {
  if (typeof window === "undefined") return "";
  return window.__OJIK_INITIAL_URL__?.search ?? window.location.search;
}

export function restoreInitialBrowserUrlIfNeeded(): void {
  if (typeof window === "undefined") return;
  const initialUrl = window.__OJIK_INITIAL_URL__;
  if (!initialUrl || !window.location.pathname.includes("__static__")) return;

  window.history.replaceState(
    window.history.state,
    "",
    `${initialUrl.pathname}${initialUrl.search}${initialUrl.hash}`,
  );
}
