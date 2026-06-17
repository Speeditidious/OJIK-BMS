"use client";

import { Suspense, use, useEffect } from "react";
import SongDetailPage from "../../SongDetailPage";
import { getInitialBrowserPathname, restoreInitialBrowserUrlIfNeeded } from "@/lib/static-route";

interface Md5SongPageProps {
  params: Promise<{ hash: string }>;
}

function Md5SongPageContent({ params }: Md5SongPageProps) {
  const { hash: routeHash } = use(params);
  const pathname = getInitialBrowserPathname();
  const pathnameHash = pathname.match(/^\/songs\/md5\/([^/?#]+)\/?$/)?.[1];
  const hash = pathnameHash ?? routeHash;

  useEffect(() => {
    restoreInitialBrowserUrlIfNeeded();
  }, []);

  return <SongDetailPage params={Promise.resolve({ fumen_id: `md5=${hash}` })} />;
}

export default function Md5SongPage(props: Md5SongPageProps) {
  return (
    <Suspense fallback={null}>
      <Md5SongPageContent {...props} />
    </Suspense>
  );
}
