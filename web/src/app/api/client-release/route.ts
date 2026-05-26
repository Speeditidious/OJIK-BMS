import { NextResponse } from "next/server";

export const revalidate = 300;

interface ClientLatestReleaseResponse {
  version: string;
  installer_url: string;
  release_page_url?: string | null;
  release_notes: string;
  asset_size_bytes?: number | null;
  asset_sha256?: string | null;
  published_at?: string;
}

async function fetchRelease(apiUrl: string, query: string): Promise<ClientLatestReleaseResponse | null> {
  let res: Response;
  try {
    res = await fetch(`${apiUrl}/client/latest-release?${query}`, {
      headers: {
        Accept: "application/json",
        "User-Agent": "OJIK-BMS",
      },
      next: { revalidate },
    });
  } catch {
    return null;
  }

  if (!res.ok) return null;
  return (await res.json()) as ClientLatestReleaseResponse | null;
}

export async function GET() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const [windowsRelease, linuxRelease] = await Promise.all([
    fetchRelease(apiUrl, "target=windows&arch=x86_64&installer_kind=nsis"),
    fetchRelease(apiUrl, "target=linux&arch=x86_64&installer_kind=appimage"),
  ]);

  const release = windowsRelease ?? linuxRelease;
  if (!release) {
    return NextResponse.json(null, { status: 200 });
  }

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
  ].filter(Boolean);

  return NextResponse.json({
    version: release.version,
    exeDownloadUrl: windowsRelease?.installer_url ?? null,
    downloads,
    publishedAt: release.published_at ?? "",
    releaseNotes: release.release_notes,
    releasePageUrl: release.release_page_url ?? "",
  });
}
