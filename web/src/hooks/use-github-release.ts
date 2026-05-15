import { useQuery } from "@tanstack/react-query";

export interface GitHubRelease {
  version: string;
  exeDownloadUrl: string | null;
  publishedAt: string;
  releaseNotes: string;
  releasePageUrl: string;
}

const RELEASE_CACHE_TIME_MS = 5 * 60 * 1000;

async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  const res = await fetch("/api/client-release");

  if (!res.ok) return null;

  return res.json();
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
