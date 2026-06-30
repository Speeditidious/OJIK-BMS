import { rename, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDirectory, "..");
const outDirectory = path.join(webRoot, "out");

function isPermissionError(error) {
  return error && (error.code === "EACCES" || error.code === "EPERM");
}

function staleExportPath(directory, now = new Date()) {
  const parent = path.dirname(directory);
  const baseName = path.basename(directory);
  const timestamp = now.toISOString().replace(/[:.]/g, "");
  return path.join(parent, `.${baseName}-stale-${timestamp}-${process.pid}`);
}

export async function cleanExportDirectory(
  directory = outDirectory,
  { remove = rm, move = rename, now = () => new Date(), warn = console.warn } = {},
) {
  try {
    await remove(directory, { recursive: true, force: true });
    return { action: "removed", path: directory };
  } catch (error) {
    if (!isPermissionError(error)) {
      throw error;
    }

    const fallbackPath = staleExportPath(directory, now());
    await move(directory, fallbackPath);
    warn(
      `Could not remove ${directory} because of filesystem permissions; moved it to ${fallbackPath} so the export can be rebuilt.`,
    );
    return { action: "moved", path: fallbackPath };
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await cleanExportDirectory();
}
