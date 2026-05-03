import type { ClientConfig } from "../../types";

export type DropClient = "lr2" | "beatoraja";

export interface SuggestedPaths {
  lr2_db_path?: string | null;
  lr2_song_db_path?: string | null;
  beatoraja_db_dir?: string | null;
  beatoraja_songdata_db_path?: string | null;
  beatoraja_songinfo_db_path?: string | null;
}

const SEPARATORS = /[\\/]/g;

function getDir(path: string): string {
  const idx = path.replace(/[\\/]+$/, "").search(/[\\/](?!.*[\\/])/);
  return idx >= 0 ? path.slice(0, idx) : path;
}

function basename(path: string): string {
  const trimmed = path.replace(/[\\/]+$/, "");
  const parts = trimmed.split(SEPARATORS);
  return parts[parts.length - 1] ?? trimmed;
}

function joinPath(dir: string, name: string): string {
  if (!dir) return name;
  const sep = dir.includes("\\") ? "\\" : "/";
  return `${dir.replace(/[\\/]+$/, "")}${sep}${name}`;
}

/**
 * Local-only suggestion based on the dropped path string. Backend
 * `detect_client_paths` (Phase 2) will refine this with real filesystem
 * checks; this function gives us reasonable defaults until then.
 */
export function suggestPathsFromHint(client: DropClient, hint: string): SuggestedPaths {
  const dir = getDir(hint);
  const base = basename(hint);
  const looksLikeFile = /\.db$/i.test(base);

  if (client === "lr2") {
    if (looksLikeFile && /score|player|^lr2|.*\.db$/i.test(base) && !/^song\.db$/i.test(base)) {
      return {
        lr2_db_path: hint,
        lr2_song_db_path: joinPath(dir, "song.db"),
      };
    }
    if (/^song\.db$/i.test(base)) {
      return { lr2_song_db_path: hint };
    }
    // Treat as folder: best-guess paths inside it.
    return {
      lr2_song_db_path: joinPath(hint, "song.db"),
    };
  }

  // beatoraja
  if (looksLikeFile && /^score(log)?\.db$/i.test(base)) {
    const playerDir = dir;
    const beaRoot = getDir(playerDir);
    return {
      beatoraja_db_dir: playerDir,
      beatoraja_songdata_db_path: joinPath(beaRoot, "songdata.db"),
      beatoraja_songinfo_db_path: joinPath(beaRoot, "songinfo.db"),
    };
  }
  if (/^songdata\.db$/i.test(base)) {
    return { beatoraja_songdata_db_path: hint };
  }
  if (/^songinfo\.db$/i.test(base)) {
    return { beatoraja_songinfo_db_path: hint };
  }
  // Folder drop: treat as bea root or player dir based on name
  if (!looksLikeFile) {
    return {
      beatoraja_db_dir: hint,
      beatoraja_songdata_db_path: joinPath(getDir(hint), "songdata.db"),
      beatoraja_songinfo_db_path: joinPath(getDir(hint), "songinfo.db"),
    };
  }
  return {};
}

/** Merge suggested paths into a ClientConfig patch only when destination is empty. */
export function mergeSuggestionPatch(
  config: ClientConfig,
  suggestion: SuggestedPaths,
  options: { overwrite?: boolean } = {},
): Partial<ClientConfig> {
  const patch: Partial<ClientConfig> = {};
  const keys: Array<keyof SuggestedPaths> = [
    "lr2_db_path",
    "lr2_song_db_path",
    "beatoraja_db_dir",
    "beatoraja_songdata_db_path",
    "beatoraja_songinfo_db_path",
  ];
  for (const key of keys) {
    const incoming = suggestion[key];
    if (!incoming) continue;
    const existing = config[key];
    if (existing && !options.overwrite) continue;
    (patch as Record<string, unknown>)[key] = incoming;
  }
  return patch;
}
