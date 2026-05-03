import { NextResponse } from "next/server";

export const revalidate = 600;

interface ClientLatestReleaseResponse {
  version: string;
  installer_url: string;
  release_page_url?: string | null;
  release_notes: string;
  asset_size_bytes?: number | null;
  asset_sha256?: string | null;
  published_at?: string;
}

export async function GET() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${apiUrl}/client/latest-release?target=windows&arch=x86_64`, {
    headers: {
      Accept: "application/json",
      "User-Agent": "OJIK-BMS",
    },
    next: { revalidate },
  });

  if (!res.ok) {
    return NextResponse.json(null, { status: 200 });
  }

  const release = (await res.json()) as ClientLatestReleaseResponse | null;
  if (!release) {
    return NextResponse.json(null, { status: 200 });
  }

  return NextResponse.json({
    version: release.version,
    exeDownloadUrl: release.installer_url,
    publishedAt: release.published_at ?? "",
    releaseNotes: release.release_notes,
    releasePageUrl: release.release_page_url ?? "",
  });
}
