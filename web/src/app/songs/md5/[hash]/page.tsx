"use client";

import { Suspense, use } from "react";
import SongDetailPage from "../../SongDetailPage";

interface Md5SongPageProps {
  params: Promise<{ hash: string }>;
}

function Md5SongPageContent({ params }: Md5SongPageProps) {
  const { hash } = use(params);
  return <SongDetailPage params={Promise.resolve({ fumen_id: `md5=${hash}` })} />;
}

export default function Md5SongPage(props: Md5SongPageProps) {
  return (
    <Suspense fallback={null}>
      <Md5SongPageContent {...props} />
    </Suspense>
  );
}
