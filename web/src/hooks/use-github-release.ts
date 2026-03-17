import { useQuery } from "@tanstack/react-query";

export interface GitHubRelease {
  version: string;
  exeDownloadUrl: string | null;
  publishedAt: string;
  releaseNotes: string;
  releasePageUrl: string;
}

async function fetchLatestRelease(): Promise<GitHubRelease | null> {
  const repo = process.env.NEXT_PUBLIC_GITHUB_REPO ?? "Speeditidious/OJIK-BMS";

  const res = await fetch(`https://api.github.com/repos/${repo}/releases/latest`, {
    headers: { Accept: "application/vnd.github+json" },
  });

  if (!res.ok) return null;

  const data = await res.json();

  const exeAsset = (data.assets ?? []).find((a: { name: string }) =>
    a.name.endsWith(".exe")
  );

  return {
    version: data.tag_name ?? "",
    exeDownloadUrl: exeAsset?.browser_download_url ?? null,
    publishedAt: data.published_at ?? "",
    releaseNotes: data.body ?? "",
    releasePageUrl: data.html_url ?? "",
  };
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
