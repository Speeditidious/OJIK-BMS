const SEGMENT_PARAM_PATTERN = /^:[A-Za-z0-9_]+$/;

function normalizePathname(pathname) {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
}

function splitPathname(pathname) {
  return normalizePathname(pathname).split("/").filter(Boolean);
}

function decodePathname(pathname) {
  try {
    return decodeURIComponent(pathname);
  } catch {
    return null;
  }
}

function isUnsafePathSegment(segment) {
  return segment === "." || segment === ".." || segment.includes("\0");
}

function matchesSource(source, pathname) {
  if (source === "/*") {
    return true;
  }

  const sourceSegments = splitPathname(source);
  const pathnameSegments = splitPathname(pathname);
  if (sourceSegments.length !== pathnameSegments.length) {
    return false;
  }

  return sourceSegments.every((segment, index) => {
    if (SEGMENT_PARAM_PATTERN.test(segment)) {
      return pathnameSegments[index].length > 0;
    }
    return segment === pathnameSegments[index];
  });
}

export function parseRedirects(redirectsText) {
  return redirectsText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const [source, destination, status] = line.split(/\s+/);
      return { source, destination, status };
    })
    .filter((rule) => rule.source && rule.destination && rule.status === "200");
}

export function createRedirectMatcher(rules) {
  return (pathname) => {
    const normalizedPathname = normalizePathname(pathname);
    const match = rules.find((rule) => matchesSource(rule.source, normalizedPathname));
    return match ? match.destination : null;
  };
}

export function getStaticFileCandidates(pathname) {
  const decodedPathname = decodePathname(pathname);
  if (!decodedPathname) {
    return [];
  }

  const segments = splitPathname(decodedPathname);
  if (segments.some(isUnsafePathSegment)) {
    return [];
  }

  if (segments.length === 0) {
    return ["index.html"];
  }

  const relativePath = segments.join("/");
  if (relativePath.endsWith(".html") || relativePath.includes(".")) {
    return [relativePath];
  }

  if (decodedPathname.endsWith("/")) {
    return [`${relativePath}/index.html`];
  }

  return [relativePath, `${relativePath}.html`, `${relativePath}/index.html`];
}
