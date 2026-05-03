import { useQuery } from "@tanstack/react-query";

export interface GitHubRelease {
  version: string;
  exeDownloadUrl: string | null;
  publishedAt: string;
  releaseNotes: string;
  releasePageUrl: string;
}

async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  const res = await fetch("/api/client-release");

  if (!res.ok) return null;

  return res.json();
}

export function useGitHubRelease() {
  return useQuery<GitHubRelease | null>({
    queryKey: ["github-release"],
    queryFn: fetchLatestRelease,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 1,
  });
}
