"use client";

import { Suspense, use } from "react";
import SongDetailPage from "../../SongDetailPage";

interface Sha256SongPageProps {
  params: Promise<{ hash: string }>;
}

function Sha256SongPageContent({ params }: Sha256SongPageProps) {
  const { hash: routeHash } = use(params);
  const pathname = typeof window === "undefined" ? "" : window.location.pathname;
  const pathnameHash = pathname.match(/^\/songs\/sha256\/([^/?#]+)\/?$/)?.[1];
  const hash = pathnameHash ?? routeHash;
  return <SongDetailPage params={Promise.resolve({ fumen_id: `sha256=${hash}` })} />;
}

export default function Sha256SongPage(props: Sha256SongPageProps) {
  return (
    <Suspense fallback={null}>
      <Sha256SongPageContent {...props} />
    </Suspense>
  );
}
