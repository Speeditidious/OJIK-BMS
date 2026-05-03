import { NextResponse } from "next/server";

export const revalidate = 600;

interface GitHubReleaseAsset {
  name: string;
  browser_download_url?: string;
}

interface GitHubReleaseResponse {
  tag_name?: string;
  published_at?: string;
  body?: string;
  html_url?: string;
  assets?: GitHubReleaseAsset[];
}

export async function GET() {
  const repo =
    process.env.GITHUB_REPO ?? process.env.NEXT_PUBLIC_GITHUB_REPO ?? "Speeditidious/OJIK-BMS";
  const res = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=1`, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "OJIK-BMS",
    },
    next: { revalidate },
  });

  if (!res.ok) {
    return NextResponse.json(null, { status: 200 });
  }

  const data = (await res.json()) as GitHubReleaseResponse[];
  const release = data[0];
  if (!release) {
    return NextResponse.json(null, { status: 200 });
  }

  const assets = release.assets ?? [];
  const exeAsset = assets.find(isTauriWindowsInstaller) ?? assets.find(isWindowsExe);

  return NextResponse.json({
    version: release.tag_name ?? "",
    exeDownloadUrl: exeAsset?.browser_download_url ?? null,
    publishedAt: release.published_at ?? "",
    releaseNotes: release.body ?? "",
    releasePageUrl: release.html_url ?? "",
  });
}

function isTauriWindowsInstaller(asset: GitHubReleaseAsset) {
  const name = asset.name.toLowerCase();
  return (
    name.startsWith("ojikbms-client-") &&
    name.includes("windows") &&
    name.endsWith(".exe")
  );
}

function isWindowsExe(asset: GitHubReleaseAsset) {
  return asset.name.toLowerCase().endsWith(".exe");
}
