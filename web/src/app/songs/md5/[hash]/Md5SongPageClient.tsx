"use client";

import { Suspense, use } from "react";
import { usePathname } from "next/navigation";
import SongDetailPage from "../../SongDetailPage";

interface Md5SongPageProps {
  params: Promise<{ hash: string }>;
}

function Md5SongPageContent({ params }: Md5SongPageProps) {
  const { hash: routeHash } = use(params);
  const pathname = usePathname();
  const pathnameHash = pathname.match(/^\/songs\/md5\/([^/?#]+)\/?$/)?.[1];
  const hash = pathnameHash ?? routeHash;
  return <SongDetailPage params={Promise.resolve({ fumen_id: `md5=${hash}` })} />;
}

export default function Md5SongPage(props: Md5SongPageProps) {
  return (
    <Suspense fallback={null}>
      <Md5SongPageContent {...props} />
    </Suspense>
  );
}
