import { readFileSync, writeFileSync } from "node:fs";
import { EOL } from "node:os";
import { resolve } from "node:path";

const rawVersion = process.argv[2] ?? process.env.GITHUB_REF_NAME;

if (!rawVersion) {
  throw new Error("Usage: node scripts/sync-version.mjs <tag-or-version>");
}

const displayVersion = rawVersion.replace(/^v/i, "");
const tauriVersion = toTauriSemver(displayVersion);

updateJson("package.json", (data) => {
  data.version = tauriVersion;
  return data;
});

updateJson("package-lock.json", (data) => {
  data.version = tauriVersion;
  if (data.packages?.[""]) {
    data.packages[""].version = tauriVersion;
  }
  return data;
});

updateJson("src-tauri/tauri.conf.json", (data) => {
  data.version = tauriVersion;
  return data;
});

updateCargoToml("src-tauri/Cargo.toml", tauriVersion);
writeGitHubOutput({
  display_version: displayVersion,
  tauri_version: tauriVersion,
  is_prerelease: String(isPrerelease(tauriVersion)),
});

console.log(`Display version: ${displayVersion}`);
console.log(`Tauri version: ${tauriVersion}`);

function toTauriSemver(version) {
  if (/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version)) {
    return version;
  }

  const dottedPrerelease = version.match(/^(\d+\.\d+\.\d+)\.([A-Za-z]+)(\d+)$/);
  if (dottedPrerelease) {
    const [, base, label, number] = dottedPrerelease;
    return `${base}-${label}.${number}`;
  }

  throw new Error(
    `Version "${version}" cannot be converted to Tauri semver. Use tags like v1.0.0 or v1.0.0.beta1.`
  );
}

function isPrerelease(version) {
  return version.includes("-");
}

function updateJson(path, updater) {
  const absolutePath = resolve(path);
  const data = JSON.parse(readFileSync(absolutePath, "utf8"));
  const nextData = updater(data);
  writeFileSync(absolutePath, `${JSON.stringify(nextData, null, 2)}${EOL}`);
}

function updateCargoToml(path, version) {
  const absolutePath = resolve(path);
  const current = readFileSync(absolutePath, "utf8");
  let foundVersion = false;
  const next = current.replace(/^version = ".*"$/m, () => {
    foundVersion = true;
    return `version = "${version}"`;
  });
  if (!foundVersion) {
    throw new Error(`Could not update package version in ${path}`);
  }
  writeFileSync(absolutePath, next);
}

function writeGitHubOutput(outputs) {
  if (!process.env.GITHUB_OUTPUT) return;
  const lines = Object.entries(outputs).map(([key, value]) => `${key}=${value}`);
  writeFileSync(process.env.GITHUB_OUTPUT, `${lines.join(EOL)}${EOL}`, { flag: "a" });
}
