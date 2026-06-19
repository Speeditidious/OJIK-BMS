import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createRedirectMatcher, getStaticFileCandidates, parseRedirects } from "./static-preview-routing.mjs";

const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".gif", "image/gif"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml; charset=utf-8"],
  [".txt", "text/plain; charset=utf-8"],
  [".webp", "image/webp"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDirectory, "..");

function readOption(name, fallback) {
  const prefix = `--${name}=`;
  const value = process.argv.find((argument) => argument.startsWith(prefix));
  return value ? value.slice(prefix.length) : fallback;
}

function getContentType(filePath) {
  return CONTENT_TYPES.get(path.extname(filePath).toLowerCase()) ?? "application/octet-stream";
}

function resolveInside(root, relativePath) {
  const resolved = path.resolve(root, relativePath);
  return resolved === root || resolved.startsWith(`${root}${path.sep}`) ? resolved : null;
}

async function findStaticFile(outDirectory, pathname) {
  for (const candidate of getStaticFileCandidates(pathname)) {
    const filePath = resolveInside(outDirectory, candidate);
    if (!filePath) {
      continue;
    }

    try {
      const stats = await stat(filePath);
      if (stats.isFile()) {
        return { filePath, size: stats.size };
      }
    } catch (error) {
      if (error?.code !== "ENOENT" && error?.code !== "ENOTDIR") {
        throw error;
      }
    }
  }

  return null;
}

async function createStaticPreviewHandler({ outDirectory, redirectsPath }) {
  const redirectsText = await readFile(redirectsPath, "utf8");
  const matchRedirect = createRedirectMatcher(parseRedirects(redirectsText));

  return async (request, response) => {
    if (request.method !== "GET" && request.method !== "HEAD") {
      response.writeHead(405, { Allow: "GET, HEAD" });
      response.end();
      return;
    }

    const requestUrl = new URL(request.url ?? "/", "http://localhost");
    const directFile = await findStaticFile(outDirectory, requestUrl.pathname);
    const redirectDestination = directFile ? null : matchRedirect(requestUrl.pathname);
    const file = directFile ?? (redirectDestination ? await findStaticFile(outDirectory, redirectDestination) : null);

    if (!file) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Length": file.size,
      "Content-Type": getContentType(file.filePath),
      "X-Static-Preview-Path": path.relative(outDirectory, file.filePath),
    });

    if (request.method === "HEAD") {
      response.end();
      return;
    }

    createReadStream(file.filePath).pipe(response);
  };
}

const port = Number(readOption("port", process.env.PORT ?? "3001"));
const host = readOption("host", process.env.HOST ?? "127.0.0.1");
const outDirectory = path.resolve(webRoot, readOption("dir", "out"));
const redirectsPath = path.resolve(webRoot, readOption("redirects", "public/_redirects"));

if (!Number.isInteger(port) || port <= 0) {
  throw new Error(`Invalid preview port: ${port}`);
}

const handler = await createStaticPreviewHandler({ outDirectory, redirectsPath });
const server = createServer((request, response) => {
  handler(request, response).catch((error) => {
    console.error(error);
    response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Static preview server error");
  });
});

server.listen(port, host, () => {
  console.log(`Static preview server listening on http://${host}:${port}`);
  console.log(`Serving ${outDirectory}`);
  console.log(`Applying redirects from ${redirectsPath}`);
});
