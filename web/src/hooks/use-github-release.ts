import { useQuery } from "@tanstack/react-query";

export interface GitHubRelease {
  version: string;
  exeDownloadUrl: string | null;
  downloads?: Array<{
    targetOs: "windows" | "linux" | string;
    label: string;
    downloadUrl: string;
    version: string;
  }>;
  publishedAt: string;
  releaseNotes: string;
  releasePageUrl: string;
}

const RELEASE_CACHE_TIME_MS = 5 * 60 * 1000;
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ClientLatestReleaseResponse {
  version: string;
  installer_url: string;
  release_page_url?: string | null;
  release_notes: string;
  asset_size_bytes?: number | null;
  asset_sha256?: string | null;
  published_at?: string;
}

async function fetchPlatformRelease(query: string): Promise<ClientLatestReleaseResponse | null> {
  const res = await fetch(`${API_URL}/client/latest-release?${query}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!res.ok) return null;
  return res.json();
}

async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  const [windowsRelease, linuxRelease] = await Promise.all([
    fetchPlatformRelease("target=windows&arch=x86_64&installer_kind=nsis"),
    fetchPlatformRelease("target=linux&arch=x86_64&installer_kind=appimage"),
  ]);

  const release = windowsRelease ?? linuxRelease;
  if (!release) return null;

  const downloads = [
    windowsRelease
      ? {
          targetOs: "windows",
          label: "Windows",
          downloadUrl: windowsRelease.installer_url,
          version: windowsRelease.version,
        }
      : null,
    linuxRelease
      ? {
          targetOs: "linux",
          label: "Linux AppImage",
          downloadUrl: linuxRelease.installer_url,
          version: linuxRelease.version,
        }
      : null,
  ].filter((item): item is NonNullable<typeof item> => item !== null);

  return {
    version: release.version,
    exeDownloadUrl: windowsRelease?.installer_url ?? null,
    downloads,
    publishedAt: release.published_at ?? "",
    releaseNotes: release.release_notes,
    releasePageUrl: release.release_page_url ?? "",
  };
}

export function useGitHubRelease() {
  return useQuery<GitHubRelease | null>({
    queryKey: ["github-release"],
    queryFn: fetchLatestRelease,
    staleTime: RELEASE_CACHE_TIME_MS,
    gcTime: RELEASE_CACHE_TIME_MS,
    retry: 1,
  });
}
